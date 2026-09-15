// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title NyayaVault Evidence Anchoring Contract
/// @notice Anchors the SHA-256 hash of a sealed evidence file on-chain so it
///         can never be silently altered without detection. The actual file,
///         case data, and custody logs stay off-chain (encrypted disk +
///         Oracle DB) — only the hash + case/evidence IDs go on-chain.
contract NyayaVault {

    struct EvidenceRecord {
        string caseNo;
        string evidenceId;
        bytes32 fileHash;       // SHA-256 hash of the sealed evidence file
        address anchoredBy;     // wallet that submitted the anchor transaction
        uint256 blockTimestamp; // chain time at anchoring
        bool exists;
    }

    address public owner;

    // key = keccak256(caseNo | evidenceId) -> record
    mapping(bytes32 => EvidenceRecord) private evidenceRegistry;

    event EvidenceAnchored(
        string indexed caseNo,
        string evidenceId,
        bytes32 fileHash,
        address indexed anchoredBy,
        uint256 blockTimestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "NyayaVault: caller is not the owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function _key(string memory caseNo, string memory evidenceId) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(caseNo, "|", evidenceId));
    }

    /// @notice Anchors a sealed evidence file's hash. Can only be done once per
    ///         evidence item — re-anchoring (e.g. after tampering) is refused.
    function anchorEvidence(string memory caseNo, string memory evidenceId, bytes32 fileHash) external onlyOwner {
        bytes32 key = _key(caseNo, evidenceId);
        require(!evidenceRegistry[key].exists, "NyayaVault: evidence already anchored");

        evidenceRegistry[key] = EvidenceRecord({
            caseNo: caseNo,
            evidenceId: evidenceId,
            fileHash: fileHash,
            anchoredBy: msg.sender,
            blockTimestamp: block.timestamp,
            exists: true
        });

        emit EvidenceAnchored(caseNo, evidenceId, fileHash, msg.sender, block.timestamp);
    }

    /// @notice Reads back the on-chain hash for tamper verification against the
    ///         DB-stored / freshly re-computed hash.
    function getEvidenceHash(string memory caseNo, string memory evidenceId)
        external
        view
        returns (bytes32 fileHash, address anchoredBy, uint256 blockTimestamp, bool exists)
    {
        EvidenceRecord memory rec = evidenceRegistry[_key(caseNo, evidenceId)];
        return (rec.fileHash, rec.anchoredBy, rec.blockTimestamp, rec.exists);
    }
}