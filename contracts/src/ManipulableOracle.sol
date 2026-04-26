// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Hackathon-grade price feed. Anyone can call `bumpPrice` — this is
/// the *intentional* vulnerability surface. Mirrors a real-world failure
/// mode where a thinly-traded TWAP can be moved by a single attacker tx.
contract ManipulableOracle {
    uint256 public price;

    event PriceBumped(address indexed by, uint256 oldPrice, uint256 newPrice);

    constructor(uint256 _initialPrice) {
        price = _initialPrice;
    }

    function bumpPrice(uint256 _newPrice) external {
        uint256 old = price;
        price = _newPrice;
        emit PriceBumped(msg.sender, old, _newPrice);
    }
}
