// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IPausable {
    function pause() external;
    function sweep(address to, address token) external;
}

/// @notice Pause oracle for a single protected protocol. Verifies a 3-of-N
/// quorum of secp256k1 signatures over a finding hash, emits an on-chain
/// attestation trail, and (optionally) sweeps collateral to a recovery vault.
///
/// Signature scheme: ETH-prefixed personal_sign over findingHash, recovered
/// via ecrecover. Agents hold ETH keys (also used for x402 payouts), so this
/// avoids a separate Ed25519 verification path.
contract Guardian {
    address public owner;
    address public protocol;
    address public recovery;

    mapping(address => bool) public authorizedAgents;
    uint256 public agentCount;
    uint256 public quorum;

    bool public paused;
    bool public revoked;

    mapping(bytes32 => bool) public processedFindings;

    event AgentSet(address indexed agent, bool authorized);
    event FindingAttested(bytes32 indexed findingHash, bytes32 teeAttestationHash);
    event Paused(bytes32 indexed findingHash);
    event SweptToRecovery(address indexed token, uint256 amount);
    event AuthorizationRevoked();
    event RecoverySet(address recovery);
    event ProtocolSet(address protocol);

    error NotOwner();
    error Revoked();
    error NotPaused();
    error AlreadyProcessed();
    error QuorumNotMet();
    error ZeroAddress();
    error BadSig();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(address _protocol, address _recovery, uint256 _quorum) {
        if (_protocol == address(0) || _recovery == address(0)) revert ZeroAddress();
        owner = msg.sender;
        protocol = _protocol;
        recovery = _recovery;
        quorum = _quorum;
    }

    function setAgent(address agent, bool authorized) external onlyOwner {
        if (agent == address(0)) revert ZeroAddress();
        bool was = authorizedAgents[agent];
        if (was == authorized) return;
        authorizedAgents[agent] = authorized;
        if (authorized) agentCount++;
        else agentCount--;
        emit AgentSet(agent, authorized);
    }

    function setRecovery(address _recovery) external onlyOwner {
        if (_recovery == address(0)) revert ZeroAddress();
        recovery = _recovery;
        emit RecoverySet(_recovery);
    }

    function setProtocol(address _protocol) external onlyOwner {
        if (_protocol == address(0)) revert ZeroAddress();
        protocol = _protocol;
        emit ProtocolSet(_protocol);
    }

    /// Permanent kill switch — once revoked, no further pauses or sweeps.
    function revokeAuthorization() external onlyOwner {
        revoked = true;
        emit AuthorizationRevoked();
    }

    /// Anyone can submit findings + sigs; quorum check is the only gate.
    /// teeAttestationHash is the 0G Compute enclave quote hash (sealed inference).
    function pause(bytes[] calldata sigs, bytes32 findingHash, bytes32 teeAttestationHash) external {
        if (revoked) revert Revoked();
        if (processedFindings[findingHash]) revert AlreadyProcessed();
        if (!verifyQuorum(sigs, findingHash)) revert QuorumNotMet();

        processedFindings[findingHash] = true;
        paused = true;

        emit FindingAttested(findingHash, teeAttestationHash);
        emit Paused(findingHash);

        IPausable(protocol).pause();
    }

    /// Sweeps a token from the protocol to the recovery vault. Owner-only,
    /// only after a quorum-triggered pause.
    function sweepToRecovery(address token) external onlyOwner {
        if (revoked) revert Revoked();
        if (!paused) revert NotPaused();
        IPausable(protocol).sweep(recovery, token);
        emit SweptToRecovery(token, 0);
    }

    /// True iff `sigs` contain ≥`quorum` distinct authorized agent signatures
    /// over the ETH-prefixed `findingHash`.
    function verifyQuorum(bytes[] calldata sigs, bytes32 findingHash) public view returns (bool) {
        bytes32 ethSigned = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", findingHash));
        address[] memory seen = new address[](sigs.length);
        uint256 count = 0;
        for (uint256 i = 0; i < sigs.length; i++) {
            address signer = _recover(ethSigned, sigs[i]);
            if (signer == address(0)) continue;
            if (!authorizedAgents[signer]) continue;
            bool dup = false;
            for (uint256 j = 0; j < count; j++) {
                if (seen[j] == signer) {
                    dup = true;
                    break;
                }
            }
            if (!dup) {
                seen[count] = signer;
                count++;
                if (count >= quorum) return true;
            }
        }
        return false;
    }

    function _recover(bytes32 hash, bytes memory sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(hash, v, r, s);
    }
}
