// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Guardian} from "../src/Guardian.sol";
import {VulnerableLendingPool} from "../src/VulnerableLendingPool.sol";
import {ManipulableOracle} from "../src/ManipulableOracle.sol";
import {MockERC20} from "../src/MockERC20.sol";

contract GuardianTest is Test {
    Guardian guardian;
    VulnerableLendingPool pool;
    ManipulableOracle oracle;
    MockERC20 collateral;
    MockERC20 debtAsset;

    address recovery = address(0xBEEF);

    uint256 a1Pk = 0xA1;
    uint256 a2Pk = 0xA2;
    uint256 a3Pk = 0xA3;
    uint256 a4Pk = 0xA4; // unauthorized
    address a1;
    address a2;
    address a3;
    address a4;

    function setUp() public {
        a1 = vm.addr(a1Pk);
        a2 = vm.addr(a2Pk);
        a3 = vm.addr(a3Pk);
        a4 = vm.addr(a4Pk);

        collateral = new MockERC20("Collateral", "COL");
        debtAsset = new MockERC20("Debt", "DBT");
        oracle = new ManipulableOracle(1e18); // start at 1.0

        pool = new VulnerableLendingPool(address(collateral), address(debtAsset), address(oracle));
        guardian = new Guardian(address(pool), recovery, 3);
        pool.setGuardian(address(guardian));

        guardian.setAgent(a1, true);
        guardian.setAgent(a2, true);
        guardian.setAgent(a3, true);
    }

    function _sign(uint256 pk, bytes32 findingHash) internal pure returns (bytes memory) {
        bytes32 ethSigned = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", findingHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, ethSigned);
        return abi.encodePacked(r, s, v);
    }

    function vm_sign_helper(uint256 pk, bytes32 h) internal pure returns (bytes memory) {
        // dummy to keep compiler happy if unused; real helper above
        return _sign(pk, h);
    }

    function test_quorumPasses_with3DistinctAuthorizedSigs() public {
        bytes32 findingHash = keccak256("oracle-manipulation-tx-0xabc");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        sigs[2] = _sign(a3Pk, findingHash);
        assertTrue(guardian.verifyQuorum(sigs, findingHash));
    }

    function test_quorumFails_below3Sigs() public {
        bytes32 findingHash = keccak256("only-two");
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        assertFalse(guardian.verifyQuorum(sigs, findingHash));
    }

    function test_quorumFails_dedupesDuplicateSigners() public {
        bytes32 findingHash = keccak256("dupe");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a1Pk, findingHash); // dup
        sigs[2] = _sign(a2Pk, findingHash);
        assertFalse(guardian.verifyQuorum(sigs, findingHash));
    }

    function test_quorumFails_unauthorizedSigner() public {
        bytes32 findingHash = keccak256("intruder");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        sigs[2] = _sign(a4Pk, findingHash); // not authorized
        assertFalse(guardian.verifyQuorum(sigs, findingHash));
    }

    function test_pause_callsProtocolAndEmitsAttestation() public {
        bytes32 findingHash = keccak256("real-finding");
        bytes32 teeHash = keccak256("tee-quote");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        sigs[2] = _sign(a3Pk, findingHash);

        vm.expectEmit(true, false, false, true, address(guardian));
        emit Guardian.FindingAttested(findingHash, teeHash);

        guardian.pause(sigs, findingHash, teeHash);

        assertTrue(guardian.paused());
        assertTrue(pool.paused());
        assertTrue(guardian.processedFindings(findingHash));
    }

    function test_pause_replayRejected() public {
        bytes32 findingHash = keccak256("replay-me");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        sigs[2] = _sign(a3Pk, findingHash);

        guardian.pause(sigs, findingHash, bytes32(0));

        vm.expectRevert(Guardian.AlreadyProcessed.selector);
        guardian.pause(sigs, findingHash, bytes32(0));
    }

    function test_pause_revokedBlocksAll() public {
        guardian.revokeAuthorization();
        bytes32 findingHash = keccak256("post-revoke");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        sigs[2] = _sign(a3Pk, findingHash);
        vm.expectRevert(Guardian.Revoked.selector);
        guardian.pause(sigs, findingHash, bytes32(0));
    }

    function test_sweepToRecovery_movesFundsAfterPause() public {
        // seed pool with debtAsset to drain
        debtAsset.mint(address(pool), 1_000e18);

        bytes32 findingHash = keccak256("sweep-flow");
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _sign(a1Pk, findingHash);
        sigs[1] = _sign(a2Pk, findingHash);
        sigs[2] = _sign(a3Pk, findingHash);
        guardian.pause(sigs, findingHash, bytes32(0));

        guardian.sweepToRecovery(address(debtAsset));
        assertEq(debtAsset.balanceOf(recovery), 1_000e18);
        assertEq(debtAsset.balanceOf(address(pool)), 0);
    }

    function test_sweep_revertsBeforePause() public {
        vm.expectRevert(Guardian.NotPaused.selector);
        guardian.sweepToRecovery(address(debtAsset));
    }
}
