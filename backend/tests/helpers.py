import hashlib

import numpy as np


class FakeEmbeddings:
    """A deterministic test-only embedding; production always uses a real model."""

    identity = "test-only"

    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            vector = np.zeros(64, dtype="float32")
            for word in text.lower().split():
                vector[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 64] += 1
            vector /= max(float(np.linalg.norm(vector)), 1e-12)
            vectors.append(vector)
        return np.array(vectors, dtype="float32").reshape((-1, 64))

    def embed_query(self, text):
        return self.embed_documents([text])[0]
