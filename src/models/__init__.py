from .vae import VoxelVAE
from .conditional_vae import ConditionalVoxelVAE

__all__ = ["VoxelVAE", "ConditionalVoxelVAE", "TransformerBlock2Vec", "load_block2vec"]


def __getattr__(name: str):
    if name in ("TransformerBlock2Vec", "load_block2vec"):
        from .block2vec import TransformerBlock2Vec, load_block2vec

        return {"TransformerBlock2Vec": TransformerBlock2Vec, "load_block2vec": load_block2vec}[name]
    raise AttributeError(name)
