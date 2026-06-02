from provider_config import DEFAULT_PROVIDER, AVAILABLE_PROVIDERS
from embedding_adapter import get_embedding


def main():
    # Every listed provider must be reachable via the adapter.
    for provider in AVAILABLE_PROVIDERS:
        result = get_embedding(provider, "hello world")
        assert isinstance(result, list) and len(result) > 0, (
            f"provider {provider!r} returned empty or non-list: {result!r}"
        )

    # The post-migration default provider must also work without error.
    default_result = get_embedding(DEFAULT_PROVIDER, "test")
    assert isinstance(default_result, list), (
        f"default provider {DEFAULT_PROVIDER!r} did not return a list"
    )

    print("OK")


if __name__ == "__main__":
    main()
