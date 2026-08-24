get_mx.py
=========

This helper resolves the lowest-preference MX record for a domain. It prints
the second argument as a fallback when DNS returns NXDOMAIN, no usable answer,
no nameserver, or a timeout.

Usage::

    python contrib/get_mx.py example.com mail.example.com

Install automx with the ``dns`` extra when using this helper::

    pip install 'automx[dns]'

Original contribution: .webflow GmbH.
