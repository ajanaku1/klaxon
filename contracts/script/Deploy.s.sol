// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {Guardian} from "../src/Guardian.sol";
import {VulnerableLendingPool} from "../src/VulnerableLendingPool.sol";
import {ManipulableOracle} from "../src/ManipulableOracle.sol";
import {AgentINFT} from "../src/AgentINFT.sol";
import {MockERC20} from "../src/MockERC20.sol";

/// Deploys the full Klaxon stack to whichever RPC is selected.
///
/// Required env:
///   PRIVATE_KEY         — deployer key (also becomes Guardian owner + AgentINFT minter)
///   AGENT_1, AGENT_2, AGENT_3 — agent ETH addresses (signers + iNFT recipients)
///   RECOVERY_VAULT      — address that receives swept funds
///   AGENT_MANIFEST_ROOT — bytes32 0G Storage root for agent manifest (Day 5; ok to pass 0x0 for now)
///   POOL_LIQUIDITY      — initial debt-asset liquidity (default 1_000_000e18)
///   ATTACKER_COLLATERAL — initial collateral seeded to deployer for attacker.s.sol (default 100e18)
contract Deploy is Script {
    struct Addrs {
        address collateral;
        address debtAsset;
        address oracle;
        address pool;
        address guardian;
        address inft;
    }

    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        Addrs memory a = _deploy(pk);
        vm.stopBroadcast();

        _logAddrs(a);
        _writeDeployment(a);
    }

    function _deploy(uint256 pk) internal returns (Addrs memory a) {
        bytes32 manifestRoot = vm.envOr("AGENT_MANIFEST_ROOT", bytes32(0));
        uint256 liquidity = vm.envOr("POOL_LIQUIDITY", uint256(1_000_000e18));
        uint256 attackerCollateral = vm.envOr("ATTACKER_COLLATERAL", uint256(100e18));

        MockERC20 collateral = new MockERC20("Klaxon Demo Collateral", "kCOL");
        MockERC20 debtAsset = new MockERC20("Klaxon Demo Debt", "kDBT");
        ManipulableOracle oracle = new ManipulableOracle(1e18);
        VulnerableLendingPool pool = new VulnerableLendingPool(address(collateral), address(debtAsset), address(oracle));
        Guardian guardian = new Guardian(address(pool), vm.envAddress("RECOVERY_VAULT"), 3);
        pool.setGuardian(address(guardian));

        guardian.setAgent(vm.envAddress("AGENT_1"), true);
        guardian.setAgent(vm.envAddress("AGENT_2"), true);
        guardian.setAgent(vm.envAddress("AGENT_3"), true);

        AgentINFT inft = new AgentINFT();
        inft.mint(vm.envAddress("AGENT_1"), manifestRoot);
        inft.mint(vm.envAddress("AGENT_2"), manifestRoot);
        inft.mint(vm.envAddress("AGENT_3"), manifestRoot);

        debtAsset.mint(address(pool), liquidity);
        collateral.mint(vm.addr(pk), attackerCollateral);

        a.collateral = address(collateral);
        a.debtAsset = address(debtAsset);
        a.oracle = address(oracle);
        a.pool = address(pool);
        a.guardian = address(guardian);
        a.inft = address(inft);
    }

    function _logAddrs(Addrs memory a) internal pure {
        console2.log("=== Klaxon deployment ===");
        console2.log("collateral", a.collateral);
        console2.log("debtAsset ", a.debtAsset);
        console2.log("oracle    ", a.oracle);
        console2.log("pool      ", a.pool);
        console2.log("guardian  ", a.guardian);
        console2.log("agentINFT ", a.inft);
    }

    function _writeDeployment(Addrs memory a) internal {
        string memory json = string.concat(
            "{\n",
            '  "chainId": ', vm.toString(block.chainid), ',\n',
            '  "collateral": "', vm.toString(a.collateral), '",\n',
            '  "debtAsset": "', vm.toString(a.debtAsset), '",\n',
            '  "oracle": "', vm.toString(a.oracle), '",\n',
            '  "pool": "', vm.toString(a.pool), '",\n',
            '  "guardian": "', vm.toString(a.guardian), '",\n',
            '  "agentINFT": "', vm.toString(a.inft), '"\n',
            "}\n"
        );
        string memory path = string.concat("./deployments/", vm.toString(block.chainid), ".json");
        vm.writeFile(path, json);
    }
}
