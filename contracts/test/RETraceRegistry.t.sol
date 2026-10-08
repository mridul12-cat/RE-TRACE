// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../contracts/RETraceRegistry.sol";
import "../contracts/IRETraceLifecycle.sol";

// Minimal test runner interface compatible with Foundry forge
interface Vm {
    function prank(address) external;
    function expectRevert(bytes calldata) external;
}

contract RETraceRegistryTest {
    RETraceRegistry public registry;
    address public owner = address(this);
    address public recycler = address(0x2222);
    address public auditor = address(0x3333);

    function setUp() public {
        registry = new RETraceRegistry();
        registry.setRole(recycler, "RECYCLER", true);
        registry.setRole(auditor, "AUDITOR", true);
    }

    function testRegisterPassport() public {
        bytes32 passportId = keccak256("DPP-EV-TEST-001");
        bytes32 bomHash = keccak256("BOM_DATA");

        bool ok = registry.registerPassport(passportId, bomHash);
        require(ok, "Registration failed");

        IRETraceRegistry.Passport memory p = registry.getPassport(passportId);
        require(p.passportId == passportId, "Passport ID mismatch");
        require(p.bomHash == bomHash, "BoM hash mismatch");
        require(p.state == LifecycleState.MANUFACTURED, "Initial state mismatch");
    }

    function testAntiReplayPassportRegistration() public {
        bytes32 passportId = keccak256("DPP-EV-TEST-001");
        bytes32 bomHash = keccak256("BOM_DATA");

        registry.registerPassport(passportId, bomHash);
        
        // Duplicate registration must revert
        try registry.registerPassport(passportId, bomHash) {
            revert("Expected revert on duplicate registration");
        } catch {
            // Expected revert
        }
    }

    function testAnchorEvidenceAndCertificate() public {
        bytes32 passportId = keccak256("DPP-EV-TEST-001");
        bytes32 eventId = keccak256("REV-EV-001");
        bytes32 commitment = keccak256("EVIDENCE_COMMITMENT");
        bytes32 certId = keccak256("POR-CERT-001");

        registry.registerPassport(passportId, keccak256("BOM"));
        registry.anchorRecyclingEvidence(eventId, passportId, commitment);

        // Transition to RECYCLING_VERIFIED
        registry.transitionLifecycleState(passportId, LifecycleState.IN_USE, bytes32(0));
        registry.transitionLifecycleState(passportId, LifecycleState.RETURNED, bytes32(0));
        registry.transitionLifecycleState(passportId, LifecycleState.RECYCLING_PENDING, bytes32(0));
        registry.transitionLifecycleState(passportId, LifecycleState.RECYCLING_VERIFIED, bytes32(0));

        // Issue certificate
        bytes32 certHash = keccak256("CERT_DATA");
        bool certOk = registry.issueCertificate(certId, eventId, passportId, certHash, commitment);
        require(certOk, "Certificate issuance failed");

        // Verify on-chain anchor
        bool verified = registry.verifyCertificateAnchor(certId, commitment);
        require(verified, "Certificate verification failed");
    }
}
