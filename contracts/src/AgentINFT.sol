// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Minimal ERC-7857-style intelligent NFT for Klaxon agents.
/// Mint-only at the hackathon stage: each iNFT points at a 0G Storage root
/// hash for an off-chain manifest `{ agentId, pubkey, analyzerCodeHash,
/// reputation: { rescues, falsePositives } }`. Owners can rotate the
/// manifest root post-rescue (dynamic reputation).
///
/// Full ERC-7857 transfer-with-reencryption-proof flow is out of scope.
contract AgentINFT {
    string public constant name = "Klaxon Analyzer Agent";
    string public constant symbol = "KLAXON";

    address public minter;
    uint256 public nextId = 1;

    mapping(uint256 => address) public ownerOf;
    mapping(uint256 => bytes32) public storageRoot;

    event Mint(uint256 indexed tokenId, address indexed to, bytes32 storageRoot);
    event ManifestUpdated(uint256 indexed tokenId, bytes32 oldRoot, bytes32 newRoot);
    event MinterTransferred(address indexed from, address indexed to);

    error NotMinter();
    error NotOwner();
    error ZeroAddress();
    error UnknownToken();

    constructor() {
        minter = msg.sender;
    }

    function mint(address to, bytes32 root) external returns (uint256) {
        if (msg.sender != minter) revert NotMinter();
        if (to == address(0)) revert ZeroAddress();
        uint256 id = nextId++;
        ownerOf[id] = to;
        storageRoot[id] = root;
        emit Mint(id, to, root);
        return id;
    }

    /// Owner of the iNFT (or the minter as a hackathon escape hatch) can
    /// rotate the manifest root — used to bump reputation after rescues.
    function updateManifest(uint256 tokenId, bytes32 newRoot) external {
        address o = ownerOf[tokenId];
        if (o == address(0)) revert UnknownToken();
        if (msg.sender != o && msg.sender != minter) revert NotOwner();
        bytes32 old = storageRoot[tokenId];
        storageRoot[tokenId] = newRoot;
        emit ManifestUpdated(tokenId, old, newRoot);
    }

    function transferMinter(address to) external {
        if (msg.sender != minter) revert NotMinter();
        if (to == address(0)) revert ZeroAddress();
        emit MinterTransferred(minter, to);
        minter = to;
    }

    function tokenURI(uint256 tokenId) external view returns (string memory) {
        if (ownerOf[tokenId] == address(0)) revert UnknownToken();
        return string(abi.encodePacked("og://", _toHex(storageRoot[tokenId])));
    }

    function _toHex(bytes32 b) internal pure returns (string memory) {
        bytes16 hexChars = 0x30313233343536373839616263646566;
        bytes memory s = new bytes(64);
        for (uint256 i = 0; i < 32; i++) {
            s[i * 2] = hexChars[uint8(b[i] >> 4)];
            s[i * 2 + 1] = hexChars[uint8(b[i] & 0x0f)];
        }
        return string(s);
    }
}
