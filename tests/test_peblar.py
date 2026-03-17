"""Asynchronous Python client for Peblar EV chargers."""

from __future__ import annotations

import pytest
from aiohttp import ClientResponse, ClientSession
from aresponses import Response, ResponsesMockServer

from peblar import Peblar, PeblarApi
from peblar.exceptions import (
    PeblarAuthenticationError,
    PeblarError,
)


async def test_identify(aresponses: ResponsesMockServer) -> None:
    """Test the identify method."""

    async def response_handler(request: ClientResponse) -> Response:
        """Response handler for this test."""
        assert not await request.text()
        return aresponses.Response(status=200)

    aresponses.add(
        "example.com",
        "/api/v1/system/identify",
        "PUT",
        response_handler,
    )
    async with Peblar(host="example.com") as peblar:
        await peblar.identify()


async def test_request_with_shared_session(aresponses: ResponsesMockServer) -> None:
    """Test a passed in shared session works as expected."""
    aresponses.add(
        "example.com",
        "/api/v1/system/identify",
        "PUT",
        aresponses.Response(status=200),
    )
    async with ClientSession() as session:
        peblar = Peblar(host="example.com", session=session)
        await peblar.identify()
        await peblar.close()


async def test_http_error400(aresponses: ResponsesMockServer) -> None:
    """Test HTTP 404 response handling."""
    aresponses.add(
        "example.com",
        "/api/v1/system/identify",
        "PUT",
        aresponses.Response(text="OMG PUPPIES!", status=400),
    )

    async with Peblar(host="example.com") as peblar:
        with pytest.raises(PeblarError):
            await peblar.identify()


async def test_ev_interface_lock_state(aresponses: ResponsesMockServer) -> None:
    """Test that lock_state is parsed from and written to the EV interface.

    NOTE: Requires hardware verification — it is unknown whether LockState
    is accepted as a writable field by PATCH /api/wlac/v1/evinterface.
    If the device returns 403, LockState is read-only via the local REST API.
    """
    ev_response = (
        '{"CpState":"State B","LockState":true,"ChargeCurrentLimit":16000,'
        '"ChargeCurrentLimitSource":"Current limiter","ChargeCurrentLimitActual":16000,'
        '"Force1Phase":false}'
    )

    async def patch_handler(request: ClientResponse) -> Response:
        """Response handler for PATCH."""
        data = await request.json()
        assert data == {"LockState": True}
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=ev_response,
        )

    aresponses.add("example.com", "/api/wlac/v1/evinterface", "PATCH", patch_handler)
    aresponses.add(
        "example.com",
        "/api/wlac/v1/evinterface",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            text=ev_response,
        ),
    )
    async with PeblarApi(host="example.com", token="test-token") as api:
        ev = await api.ev_interface(lock_state=True)
    assert ev.lock_state is True


async def test_unauthenticated_response(aresponses: ResponsesMockServer) -> None:
    """Test authentication failure."""
    aresponses.add(
        "example.com",
        "/api/v1/system/identify",
        "PUT",
        aresponses.Response(status=401),
    )

    async with Peblar(host="example.com") as peblar:
        with pytest.raises(PeblarAuthenticationError):
            await peblar.identify()
