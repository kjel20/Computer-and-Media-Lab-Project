import logging
from typing import Any
import torch
from sentence_transformers import SentenceTransformer, util
from config import EMBEDDING_MODEL, MIN_SIMILARITY_SCORE, TOP_K_RESULTS
logger = logging.getLogger(__name__)

class Retriever:
    """Creates note-chunk embeddings and retrieves relevant style examples."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        top_k: int = TOP_K_RESULTS,
        min_similarity_score: float = MIN_SIMILARITY_SCORE,
    ) -> None:
        self.model_name = model_name
        self.top_k = top_k
        self.min_similarity_score = min_similarity_score
        self.chunks: list[dict[str, Any]] = []
        self.chunk_embeddings: torch.Tensor | None = None

        self._validate_settings()

        logger.info("Loading embedding model: %s", self.model_name)

        try:
            self.model = SentenceTransformer(self.model_name)
        except Exception as error:
            logger.exception("Failed to load embedding model: %s", self.model_name)
            raise RuntimeError(
                "The embedding model could not be loaded. Check that "
                "sentence-transformers is installed and that the model "
                "has been downloaded successfully."
            ) from error

        logger.info("Embedding model loaded successfully.")

    def index_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Validate chunks and create their in-memory embeddings."""

        if not isinstance(chunks, list):
            raise TypeError("Chunks must be provided as a list.")

        valid_chunks = []

        for position, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                logger.warning("Skipping chunk %d because it is not a dictionary.", position)
                continue

            text = chunk.get("text", "")

            if not isinstance(text, str) or not text.strip():
                logger.warning("Skipping chunk %d because it has no usable text.", position)
                continue

            valid_chunk = chunk.copy()
            valid_chunk["text"] = text.strip()
            valid_chunk.setdefault("source", "unknown")
            valid_chunk.setdefault("chunk_id", position)
            valid_chunk.setdefault("file_type", "")
            valid_chunks.append(valid_chunk)

        if not valid_chunks:
            self.clear_index()
            logger.warning("No valid note chunks were provided.")
            return 0

        chunk_texts = [chunk["text"] for chunk in valid_chunks]
        logger.info("Creating embeddings for %d note chunk(s).", len(chunk_texts))

        try:
            embeddings = self.model.encode(
                chunk_texts,
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as error:
            self.clear_index()
            logger.exception("Failed to create note-chunk embeddings.")
            raise RuntimeError(
                "The note chunks could not be converted into embeddings."
            ) from error

        self.chunks = valid_chunks
        self.chunk_embeddings = embeddings
        logger.info("Successfully indexed %d note chunk(s).", len(self.chunks))
        return len(self.chunks)

    def retrieve(
        self,
        transcript: str,
        top_k: int | None = None,
        min_similarity_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return relevant note chunks, with style fallbacks when needed."""

        transcript = self._validate_transcript(transcript)

        if not self.is_indexed():
            logger.warning(
                "Retrieval was requested before chunks were indexed."
            )
            return []

        result_limit = self.top_k if top_k is None else top_k
        score_threshold = (
            self.min_similarity_score
            if min_similarity_score is None
            else min_similarity_score
        )

        self._validate_retrieval_arguments(
            result_limit,
            score_threshold,
        )

        logger.info(
            "Creating embedding for the lecture transcript."
        )

        try:
            transcript_embedding = self.model.encode(
                transcript,
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

        except Exception as error:
            logger.exception(
                "Failed to create transcript embedding."
            )

            raise RuntimeError(
                "The transcript could not be converted into an embedding."
            ) from error

        if transcript_embedding.dim() == 1:
            transcript_embedding = (
                transcript_embedding.unsqueeze(0)
            )

        similarity_scores = util.cos_sim(
            transcript_embedding,
            self.chunk_embeddings,
        )[0]

        available_results = min(
            result_limit,
            len(self.chunks),
        )

        top_scores, top_indices = torch.topk(
            similarity_scores,
            k=available_results,
        )

        ranked_results = []

        for score_tensor, index_tensor in zip(
            top_scores,
            top_indices,
        ):
            score = float(score_tensor.item())
            index = int(index_tensor.item())

            result = self.chunks[index].copy()
            result["score"] = score
            ranked_results.append(result)

        if ranked_results:
            logger.info(
                "Retrieval score range "
                "(highest=%.4f, lowest=%.4f, threshold=%.2f).",
                ranked_results[0]["score"],
                ranked_results[-1]["score"],
                score_threshold,
            )

        filtered_results = [
            result
            for result in ranked_results
            if result["score"] >= score_threshold
        ]

        if filtered_results:
            logger.info(
                "Retrieved %d relevant chunk(s).",
                len(filtered_results),
            )
            return filtered_results

        logger.warning(
            "No chunks met the %.2f similarity threshold. "
            "Returning %d top-ranked chunk(s) as organizational-style fallbacks.",
            score_threshold,
            len(ranked_results),
        )
        return ranked_results

    def index_and_retrieve(
        self,
        chunks: list[dict[str, Any]],
        transcript: str,
        top_k: int | None = None,
        min_similarity_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """Index chunks and immediately search them."""

        if self.index_chunks(chunks) == 0:
            return []

        return self.retrieve(
            transcript=transcript,
            top_k=top_k,
            min_similarity_score=min_similarity_score,
        )

    def is_indexed(self) -> bool:
        """Return True when chunks and embeddings are available."""

        return (
            bool(self.chunks)
            and self.chunk_embeddings is not None
            and len(self.chunk_embeddings) > 0
        )

    def get_indexed_chunk_count(self) -> int:
        """Return the number of currently indexed chunks."""

        return len(self.chunks)

    def get_sources(self) -> list[str]:
        """Return the unique filenames represented in the current index."""

        return sorted({
            str(chunk.get("source", "unknown"))
            for chunk in self.chunks
        })

    def clear_index(self) -> None:
        """Remove all indexed chunks and embeddings from memory."""

        self.chunks = []
        self.chunk_embeddings = None
        logger.info("Retriever index cleared.")

    def _validate_settings(self) -> None:
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError("Embedding model name must be a non-empty string.")

        self._validate_retrieval_arguments(
            self.top_k,
            self.min_similarity_score,
        )

    def _validate_transcript(self, transcript: str) -> str:
        if not isinstance(transcript, str):
            raise TypeError("Transcript must be a string.")

        transcript = transcript.strip()

        if not transcript:
            raise ValueError("Transcript cannot be empty.")

        return transcript

    def _validate_retrieval_arguments(self, top_k: int, min_similarity_score: float,) -> None:
        if not isinstance(top_k, int):
            raise TypeError("top_k must be an integer.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if not isinstance(min_similarity_score, (int, float)):
            raise TypeError("Minimum similarity score must be numeric.")

        if not -1.0 <= min_similarity_score <= 1.0:
            raise ValueError(
                "Minimum similarity score must be between -1.0 and 1.0."
            )