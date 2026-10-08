// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

enum LifecycleState {
    MANUFACTURED,
    IN_USE,
    RETURNED,
    RECYCLING_PENDING,
    RECYCLING_VERIFIED,
    MATERIALS_RECOVERED,
    FLAGGED
}

/**
 * @title IRETraceLifecycle
 * @notice Canonical interface for the RE:TRACE Lifecycle State Transition Controller.
 * @dev Enforces guard conditions and role-based permissions on product transitions.
 */
interface IRETraceLifecycle {

    event StateTransitionValidated(
        bytes32 indexed passportId,
        LifecycleState indexed fromState,
        LifecycleState indexed toState,
        address indexed caller
    );

    function validateAndTransition(
        bytes32 passportId,
        LifecycleState targetState,
        bytes32 proofHash
    ) external returns (bool);

    function isTransitionAllowed(
        LifecycleState fromState,
        LifecycleState toState,
        address actor
    ) external view returns (bool);

    function getLifecycleState(bytes32 passportId) external view returns (LifecycleState);
}
