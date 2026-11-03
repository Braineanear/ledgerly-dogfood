from ledgerly_shared import PlaceholderModel
from ledgerly_shared.models import PlaceholderModel as ModelFromModule


def test_placeholder_model_is_importable() -> None:
    model = PlaceholderModel(identifier="placeholder")

    assert ModelFromModule is PlaceholderModel
    assert model.identifier == "placeholder"
