// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract LivestockNFT {
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);

    mapping(uint256 => string) private _tokenURIs;
    mapping(uint256 => address) public ownerOf;

    uint256 public nextId = 1;

    function tokenURI(uint256 tokenId) public view returns (string memory) {
        return _tokenURIs[tokenId];
    }

    function mintLivestockNFT(address to, string memory uri) public returns(uint256) {
        uint256 tokenId = nextId;
        nextId++;

        ownerOf[tokenId] = to;
        _tokenURIs[tokenId] = uri;

        emit Transfer(address(0), to, tokenId);
        return tokenId;
    }
}
