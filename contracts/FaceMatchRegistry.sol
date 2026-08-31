// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title FaceMatchRegistry
/// @notice An append-only registry of face-match evidence hashes.
/// @dev The chain's role here is a tamper-evident timestamp, not a database. There is no update
///      path and no delete path: mutability would defeat the entire purpose of the record.
///
///      This contract proves WHEN a claim was recorded and that it has not changed since. It does
///      not, and cannot, prove that the claim is true. Anchoring an incorrect match produces a
///      permanent, tamper-evident record of an incorrect match.
contract FaceMatchRegistry {
    struct Record {
        bytes32 evidenceHash;
        string postUrl;
        uint16 similarityBps;
        uint64 timestamp;
        address submitter;
    }

    Record[] private _records;

    /// @param similarityBps Cosine similarity times 10000. A RAW COSINE ENCODING -- not a
    ///        probability and not a confidence percentage. 10000 means cosine 1.0.
    event MatchAnchored(
        uint256 indexed id,
        bytes32 indexed evidenceHash,
        string postUrl,
        uint16 similarityBps,
        address indexed submitter
    );

    /// @notice Record an evidence hash. Append-only.
    /// @dev postUrl is stored in cleartext deliberately. It costs gas, but it lets a reviewer open
    ///      the transaction on a block explorer and read the matched post directly.
    function anchor(bytes32 evidenceHash, string calldata postUrl, uint16 similarityBps)
        external
        returns (uint256 id)
    {
        require(evidenceHash != bytes32(0), "empty hash");
        require(bytes(postUrl).length > 0, "empty url");

        id = _records.length;
        _records.push(
            Record({
                evidenceHash: evidenceHash,
                postUrl: postUrl,
                similarityBps: similarityBps,
                timestamp: uint64(block.timestamp),
                submitter: msg.sender
            })
        );
        emit MatchAnchored(id, evidenceHash, postUrl, similarityBps, msg.sender);
    }

    function get(uint256 id) external view returns (Record memory) {
        require(id < _records.length, "no such record");
        return _records[id];
    }

    /// @notice Present for completeness. The CLI deliberately uses get() instead, so the hash
    ///         comparison is visible to a viewer rather than hidden inside a chain-side boolean.
    function verify(uint256 id, bytes32 candidate) external view returns (bool) {
        require(id < _records.length, "no such record");
        return _records[id].evidenceHash == candidate;
    }

    function count() external view returns (uint256) {
        return _records.length;
    }
}
