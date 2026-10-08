// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IRETraceLifecycle.sol";

/**
 * @title IRETraceRegistry
 * @notice Canonical interface for RE:TRACE Circular Economy & Digital Product Passport Registry.
 * @dev Governs product registration, evidence anchoring, lifecycle progression, and certificate issuance.
 */
interface IRETraceRegistry {
    struct Passport {
        bytes32 passportId;
        LifecycleState state;
        address manufacturer;
        uint256 registeredAt;
        bytes32 bomHash;
    }

    struct RecyclingEvent {
        bytes32 eventId;
        bytes32 passportId;
        bytes32 evidenceCommitment;
        address recycler;
        uint256 timestamp;
        bool isVerified;
        bool isFlagged;
    }

    struct Certificate {
        bytes32 certificateId;
        bytes32 eventId;
        bytes32 passportId;
        bytes32 certificateHash;
        bytes32 evidenceCommitment;
        address issuer;
        uint256 issuedAt;
    }

    // --- Events ---
    event PassportRegistered(
        bytes32 indexed passportId,
        address indexed manufacturer,
        bytes32 bomHash,
        uint256 timestamp
    );

    event LifecycleStateChanged(
        bytes32 indexed passportId,
        LifecycleState indexed previousState,
        LifecycleState indexed newState,
        address indexed actor
    );

    event RecyclingEvidenceAnchored(
        bytes32 indexed eventId,
        bytes32 indexed passportId,
        bytes32 evidenceCommitment,
        address indexed recycler,
        uint256 timestamp
    );

    event ProductFlagged(
        bytes32 indexed passportId,
        bytes32 indexed eventId,
        string reason
    );

    event FlagResolved(
        bytes32 indexed passportId,
        LifecycleState targetState,
        address indexed auditor,
        string notes
    );

    event CertificateIssued(
        bytes32 indexed certificateId,
        bytes32 indexed eventId,
        bytes32 indexed passportId,
        bytes32 certHash,
        bytes32 evidenceCommitment,
        uint256 timestamp
    );

    // --- State-Modifying Functions ---
    function registerPassport(bytes32 passportId, bytes32 bomHash) external returns (bool);

    function transitionLifecycleState(
        bytes32 passportId,
        LifecycleState newState,
        bytes32 evidenceRef
    ) external returns (bool);

    function anchorRecyclingEvidence(
        bytes32 eventId,
        bytes32 passportId,
        bytes32 evidenceCommitment
    ) external returns (bool);

    function flagProduct(
        bytes32 passportId,
        bytes32 eventId,
        string calldata reason
    ) external returns (bool);

    function resolveFlag(
        bytes32 passportId,
        LifecycleState targetState,
        string calldata notes
    ) external returns (bool);

    function issueCertificate(
        bytes32 certificateId,
        bytes32 eventId,
        bytes32 passportId,
        bytes32 certHash,
        bytes32 evidenceCommitment
    ) external returns (bool);

    // --- View Functions ---
    function getPassport(bytes32 passportId) external view returns (Passport memory);

    function getRecyclingEvent(bytes32 eventId) external view returns (RecyclingEvent memory);

    function getCertificate(bytes32 certificateId) external view returns (Certificate memory);

    function verifyCertificateAnchor(
        bytes32 certificateId,
        bytes32 expectedCommitment
    ) external view returns (bool);
}
