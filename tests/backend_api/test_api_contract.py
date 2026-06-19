import pytest
from backend.api_contract import APIContract

@pytest.mark.parametrize("payload, expected_error", [
    ({"missing_field": "value"}, "Missing required field: 'required_field'"),
    ({"required_field": None}, "Invalid value for field: 'required_field'")
])
def test_api_contract_negative_cases(payload, expected_error):
    with pytest.raises(APIContract.Error) as exc_info:
        APIContract.validate(payload)
    assert str(exc_info.value) == expected_error

@pytest.mark.asyncio
async def test_api_contract_async_wrapper():
    async def async_helper():
        return APIContract.validate({"required_field": "value"})
    result = await async_helper()
    assert result == {"required_field": "value"}
