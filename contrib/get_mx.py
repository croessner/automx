#!/usr/bin/env python3
"""Print the primary MX hostname, or a caller-provided fallback."""

from __future__ import annotations

import argparse

import dns.exception
import dns.resolver


def primary_mx(domain: str, fallback: str) -> str:
    """Resolve the lowest-preference MX without hiding programming errors."""
    try:
        answers = dns.resolver.resolve(domain.rstrip("."), "MX")
    except (
        dns.exception.Timeout,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.resolver.NXDOMAIN,
    ):
        return fallback

    records = sorted(answers, key=lambda answer: (answer.preference, str(answer.exchange)))
    return str(records[0].exchange).rstrip(".") if records else fallback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument("fallback")
    args = parser.parse_args()
    print(primary_mx(args.domain, args.fallback))


if __name__ == "__main__":
    main()
