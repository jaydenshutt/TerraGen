"""Tests for subnet CIDR planning."""

import ipaddress

import pytest

from terragen.cidrs import compute_subnet_cidrs, summarize_address_space, validate_custom_subnets


def test_basic_split_two_az():
    public, private = compute_subnet_cidrs("10.0.0.0/16", 2)
    assert len(public) == 2
    assert len(private) == 2
    vpc = ipaddress.ip_network("10.0.0.0/16")
    for c in public + private:
        assert ipaddress.ip_network(c).subnet_of(vpc)


def test_three_az():
    public, private = compute_subnet_cidrs("10.0.0.0/16", 3)
    assert len(public) == 3
    assert len(private) == 3
    # no overlaps
    nets = [ipaddress.ip_network(c) for c in public + private]
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            assert not a.overlaps(b)


def test_single_az():
    public, private = compute_subnet_cidrs("10.0.0.0/16", 1)
    assert len(public) == 1
    assert len(private) == 1


def test_rejects_zero_az():
    with pytest.raises(ValueError):
        compute_subnet_cidrs("10.0.0.0/16", 0)


def test_rejects_too_many_az():
    with pytest.raises(ValueError):
        compute_subnet_cidrs("10.0.0.0/16", 7)


def test_small_cidr_still_works():
    public, private = compute_subnet_cidrs("10.0.0.0/24", 2)
    assert len(public) == 2
    assert all(ipaddress.ip_network(c).prefixlen <= 28 for c in public + private)


def test_validate_custom_ok():
    validate_custom_subnets(
        "10.0.0.0/16",
        ["10.0.0.0/24", "10.0.1.0/24"],
        ["10.0.10.0/24", "10.0.11.0/24"],
    )


def test_validate_custom_outside_vpc():
    with pytest.raises(ValueError, match="not inside"):
        validate_custom_subnets(
            "10.0.0.0/16",
            ["11.0.0.0/24"],
            ["10.0.10.0/24"],
        )


def test_validate_custom_overlap():
    with pytest.raises(ValueError, match="Overlapping"):
        validate_custom_subnets(
            "10.0.0.0/16",
            ["10.0.0.0/24"],
            ["10.0.0.0/25"],
        )


def test_summarize():
    s = summarize_address_space("10.0.0.0/16", ["10.0.0.0/24"], ["10.0.1.0/24"])
    assert s["public_count"] == 1
    assert s["vpc_cidr"] == "10.0.0.0/16"
