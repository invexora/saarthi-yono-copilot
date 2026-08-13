"""Compatibility wrapper around the governed manifest-backed policy catalog."""

from backend.policy_catalog import PolicyCatalog


class DocumentVectorIngester(PolicyCatalog):
    def __init__(self, index_name="saarthi-kb", manifest_path=None, minimum_approval="approved"):
        self.index_name = index_name
        super().__init__(manifest_path=manifest_path, minimum_approval=minimum_approval)

    def connect_vector_db(self):
        return True

    def ingest_documents(self):
        return {
            "manifest_version": self.manifest_version,
            "validated_documents": len(self.policies),
        }


if __name__ == "__main__":
    ingester = DocumentVectorIngester()
    print(ingester.ingest_documents())
    print(ingester.retrieve_policy("Data minimization and right to erasure"))
