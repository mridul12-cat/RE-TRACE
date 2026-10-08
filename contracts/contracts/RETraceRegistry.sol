// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IRETraceRegistry.sol";
import "./IRETraceLifecycle.sol";

/**
 * @title RETraceRegistry
 * @notice Canonical implementation of the RE:TRACE Circular Economy & Digital Product Passport Registry.
 * @dev Enforces role-based access control, anti-replay guards, lifecycle state transitions,
 *      evidence integrity commitments, and duplicate certificate prevention.
 */
contract RETraceRegistry is IRETraceRegistry, IRETraceLifecycle {
    // --- Roles ---
    address public owner;
    mapping(address => bool) public verifiers;
    mapping(address => bool) public auditors;
    mapping(address => bool) public recyclers;
    mapping(address => bool) public manufacturers;

    // --- Storage ---
    mapping(bytes32 => Passport) private _passports;
    mapping(bytes32 => bool) private _passportExists;

    mapping(bytes32 => RecyclingEvent) private _events;
    mapping(bytes32 => bool) private _eventExists;

    mapping(bytes32 => Certificate) private _certificates;
    mapping(bytes32 => bool) private _certificateExists;
    mapping(bytes32 => bytes32) private _eventToCertificate; // eventId => certificateId (Anti-Replay)

    mapping(bytes32 => string) private _flaggedReasons;

    // --- Modifiers ---
    modifier onlyOwner() {
        require(msg.sender == owner, "RETrace: caller is not the owner");
        _;
    }

    modifier onlyAuditor() {
        require(auditors[msg.sender] || msg.sender == owner, "RETrace: caller is not an authorized auditor");
        _;
    }

    constructor() {
        owner = msg.sender;
        verifiers[msg.sender] = true;
        auditors[msg.sender] = true;
        recyclers[msg.sender] = true;
        manufacturers[msg.sender] = true;
    }

    function setRole(address account, string calldata role, bool status) external onlyOwner {
        bytes32 roleHash = keccak256(bytes(role));
        if (roleHash == keccak256(bytes("VERIFIER"))) {
            verifiers[account] = status;
        } else if (roleHash == keccak256(bytes("AUDITOR"))) {
            auditors[account] = status;
        } else if (roleHash == keccak256(bytes("RECYCLER"))) {
            recyclers[account] = status;
        } else if (roleHash == keccak256(bytes("MANUFACTURER"))) {
            manufacturers[account] = status;
        } else {
            revert("RETrace: unknown role");
        }
    }

    // --- IRETraceRegistry Implementations ---

    function registerPassport(bytes32 passportId, bytes32 bomHash) external override returns (bool) {
        require(passportId != bytes32(0), "RETrace: invalid passport ID");
        require(!_passportExists[passportId], "RETrace: passport already registered");

        _passports[passportId] = Passport({
            passportId: passportId,
            state: LifecycleState.MANUFACTURED,
            manufacturer: msg.sender,
            registeredAt: block.timestamp,
            bomHash: bomHash
        });
        _passportExists[passportId] = true;

        emit PassportRegistered(passportId, msg.sender, bomHash, block.timestamp);
        return true;
    }

    function transitionLifecycleState(
        bytes32 passportId,
        LifecycleState newState,
        bytes32 evidenceRef
    ) external override returns (bool) {
        require(_passportExists[passportId], "RETrace: passport does not exist");
        Passport storage p = _passports[passportId];
        LifecycleState currentState = p.state;

        require(currentState != newState, "RETrace: anti-replay rejected, already in target state");
        require(_isTransitionValid(currentState, newState, msg.sender), "RETrace: unauthorized or illegal state transition");

        p.state = newState;

        emit LifecycleStateChanged(passportId, currentState, newState, msg.sender);
        emit StateTransitionValidated(passportId, currentState, newState, msg.sender);
        return true;
    }

    function anchorRecyclingEvidence(
        bytes32 eventId,
        bytes32 passportId,
        bytes32 evidenceCommitment
    ) external override returns (bool) {
        require(eventId != bytes32(0), "RETrace: invalid event ID");
        require(_passportExists[passportId], "RETrace: passport does not exist");
        require(!_eventExists[eventId], "RETrace: recycling event already anchored (replay rejected)");
        require(evidenceCommitment != bytes32(0), "RETrace: invalid evidence commitment");

        _events[eventId] = RecyclingEvent({
            eventId: eventId,
            passportId: passportId,
            evidenceCommitment: evidenceCommitment,
            recycler: msg.sender,
            timestamp: block.timestamp,
            isVerified: true,
            isFlagged: false
        });
        _eventExists[eventId] = true;

        emit RecyclingEvidenceAnchored(eventId, passportId, evidenceCommitment, msg.sender, block.timestamp);
        return true;
    }

    function flagProduct(
        bytes32 passportId,
        bytes32 eventId,
        string calldata reason
    ) external override returns (bool) {
        require(_passportExists[passportId], "RETrace: passport does not exist");
        Passport storage p = _passports[passportId];
        LifecycleState prev = p.state;
        p.state = LifecycleState.FLAGGED;
        _flaggedReasons[passportId] = reason;

        if (eventId != bytes32(0) && _eventExists[eventId]) {
            _events[eventId].isFlagged = true;
            _events[eventId].isVerified = false;
        }

        emit ProductFlagged(passportId, eventId, reason);
        emit LifecycleStateChanged(passportId, prev, LifecycleState.FLAGGED, msg.sender);
        return true;
    }

    function resolveFlag(
        bytes32 passportId,
        LifecycleState targetState,
        string calldata notes
    ) external override onlyAuditor returns (bool) {
        require(_passportExists[passportId], "RETrace: passport does not exist");
        Passport storage p = _passports[passportId];
        require(p.state == LifecycleState.FLAGGED, "RETrace: product is not in FLAGGED state");
        require(targetState != LifecycleState.FLAGGED, "RETrace: target state must not be FLAGGED");
        require(bytes(notes).length > 0, "RETrace: resolution notes required");

        p.state = targetState;
        delete _flaggedReasons[passportId];

        emit FlagResolved(passportId, targetState, msg.sender, notes);
        emit LifecycleStateChanged(passportId, LifecycleState.FLAGGED, targetState, msg.sender);
        return true;
    }

    function issueCertificate(
        bytes32 certificateId,
        bytes32 eventId,
        bytes32 passportId,
        bytes32 certHash,
        bytes32 evidenceCommitment
    ) external override returns (bool) {
        require(certificateId != bytes32(0), "RETrace: invalid certificate ID");
        require(!_certificateExists[certificateId], "RETrace: certificate already issued");
        require(_eventExists[eventId], "RETrace: recycling event not anchored");
        require(_passportExists[passportId], "RETrace: passport not found");
        require(_eventToCertificate[eventId] == bytes32(0), "RETrace: certificate already issued for this recycling event");

        RecyclingEvent storage ev = _events[eventId];
        require(ev.isVerified && !ev.isFlagged, "RETrace: event is not verified or is flagged");
        require(ev.evidenceCommitment == evidenceCommitment, "RETrace: evidence commitment mismatch");

        Passport storage p = _passports[passportId];
        require(p.state == LifecycleState.RECYCLING_VERIFIED, "RETrace: product must be in RECYCLING_VERIFIED state");

        _certificates[certificateId] = Certificate({
            certificateId: certificateId,
            eventId: eventId,
            passportId: passportId,
            certificateHash: certHash,
            evidenceCommitment: evidenceCommitment,
            issuer: msg.sender,
            issuedAt: block.timestamp
        });
        _certificateExists[certificateId] = true;
        _eventToCertificate[eventId] = certificateId;

        emit CertificateIssued(certificateId, eventId, passportId, certHash, evidenceCommitment, block.timestamp);
        return true;
    }

    // --- IRETraceLifecycle Implementations ---

    function validateAndTransition(
        bytes32 passportId,
        LifecycleState targetState,
        bytes32 proofHash
    ) external override returns (bool) {
        return this.transitionLifecycleState(passportId, targetState, proofHash);
    }

    function isTransitionAllowed(
        LifecycleState fromState,
        LifecycleState toState,
        address actor
    ) external view override returns (bool) {
        return _isTransitionValid(fromState, toState, actor);
    }

    function getLifecycleState(bytes32 passportId) external view override returns (LifecycleState) {
        require(_passportExists[passportId], "RETrace: passport does not exist");
        return _passports[passportId].state;
    }

    // --- View Functions ---

    function getPassport(bytes32 passportId) external view override returns (Passport memory) {
        require(_passportExists[passportId], "RETrace: passport does not exist");
        return _passports[passportId];
    }

    function getRecyclingEvent(bytes32 eventId) external view override returns (RecyclingEvent memory) {
        require(_eventExists[eventId], "RETrace: event does not exist");
        return _events[eventId];
    }

    function getCertificate(bytes32 certificateId) external view override returns (Certificate memory) {
        require(_certificateExists[certificateId], "RETrace: certificate does not exist");
        return _certificates[certificateId];
    }

    function verifyCertificateAnchor(
        bytes32 certificateId,
        bytes32 expectedCommitment
    ) external view override returns (bool) {
        if (!_certificateExists[certificateId]) {
            return false;
        }
        return _certificates[certificateId].evidenceCommitment == expectedCommitment;
    }

    function getFlagReason(bytes32 passportId) external view returns (string memory) {
        return _flaggedReasons[passportId];
    }

    // --- Internal Helpers ---

    function _isTransitionValid(
        LifecycleState fromState,
        LifecycleState toState,
        address actor
    ) internal view returns (bool) {
        if (fromState == toState) {
            return false;
        }

        // State Machine rules matching ADR-001:
        if (fromState == LifecycleState.MANUFACTURED && toState == LifecycleState.IN_USE) {
            return manufacturers[actor] || actor == owner;
        }
        if (fromState == LifecycleState.IN_USE && toState == LifecycleState.RETURNED) {
            return true; // Collection agent or logistics
        }
        if (fromState == LifecycleState.RETURNED && toState == LifecycleState.RECYCLING_PENDING) {
            return recyclers[actor] || actor == owner;
        }
        if (fromState == LifecycleState.RECYCLING_PENDING && toState == LifecycleState.RECYCLING_VERIFIED) {
            return verifiers[actor] || actor == owner;
        }
        if (fromState == LifecycleState.RECYCLING_PENDING && toState == LifecycleState.FLAGGED) {
            return verifiers[actor] || actor == owner;
        }
        if (fromState == LifecycleState.RECYCLING_VERIFIED && toState == LifecycleState.MATERIALS_RECOVERED) {
            return recyclers[actor] || actor == owner;
        }
        if (fromState == LifecycleState.RECYCLING_VERIFIED && toState == LifecycleState.FLAGGED) {
            return verifiers[actor] || auditors[actor] || actor == owner;
        }
        if (fromState == LifecycleState.FLAGGED && toState == LifecycleState.RECYCLING_VERIFIED) {
            return auditors[actor] || actor == owner;
        }

        return false;
    }
}
