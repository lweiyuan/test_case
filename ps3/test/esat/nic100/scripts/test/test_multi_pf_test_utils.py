#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""Unit tests for multi_pf_test_utils."""

import os
import sys
import unittest

# Ensure project import paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import add_syspath  # noqa: F401

from scripts.script_libs.multi_pf_test_utils import (
    build_ib_read_bw_client_cmd,
    build_ib_read_bw_server_cmd,
    build_query_commands,
    is_pport,
    parse_bandwidth_from_output,
)


class TestParseBandwidthFromOutput(unittest.TestCase):
    def test_empty_output_returns_zero(self):
        self.assertEqual(parse_bandwidth_from_output(""), 0.0)

    def test_no_matching_lines_returns_zero(self):
        self.assertEqual(parse_bandwidth_from_output("hello world\nno data"), 0.0)

    def test_single_line_returns_its_bandwidth(self):
        output = "# header\n 1000 64 1 1234.5 10.0\n"
        self.assertAlmostEqual(parse_bandwidth_from_output(output), 1234.5)

    def test_excludes_last_line_and_averages(self):
        output = (
            " 1000 64 1 1000.0 10.0\n"
            " 1001 64 1 2000.0 10.0\n"
            " 1002 64 1 3000.0 10.0\n"
        )
        # sample_lines=1 -> only line 2 (the second-to-last)
        self.assertAlmostEqual(parse_bandwidth_from_output(output, sample_lines=1), 2000.0)

    def test_averages_multiple_recent_lines(self):
        output = (
            " 1000 64 1 1000.0 10.0\n"
            " 1001 64 1 2000.0 10.0\n"
            " 1002 64 1 3000.0 10.0\n"
            " 1003 64 1 4000.0 10.0\n"
        )
        # sample_lines=2 -> average of line 2 (2000) and line 3 (3000), excluding last
        self.assertAlmostEqual(parse_bandwidth_from_output(output, sample_lines=2), 2500.0)

    def test_ignores_non_numeric_columns(self):
        output = " 1000 64 1 abc 10.0\n"
        self.assertEqual(parse_bandwidth_from_output(output), 0.0)


class TestIsPport(unittest.TestCase):
    def test_mlx5_0_is_pport(self):
        self.assertTrue(is_pport("mlx5_0"))

    def test_mlx5_1_is_pport(self):
        self.assertTrue(is_pport("mlx5_1"))

    def test_mlx5_2_is_not_pport(self):
        self.assertFalse(is_pport("mlx5_2"))

    def test_unknown_device_is_not_pport(self):
        self.assertFalse(is_pport("mlx5_99"))


class TestBuildIbReadBwServerCmd(unittest.TestCase):
    def test_builds_expected_command(self):
        expected = "nohup ib_read_bw -d mlx5_0 -p 19000 -b --run_infinitely -D 1 -F > /tmp/s.log 2>&1 &"
        self.assertEqual(build_ib_read_bw_server_cmd("mlx5_0", 19000, "/tmp/s.log"), expected)


class TestBuildIbReadBwClientCmd(unittest.TestCase):
    def test_builds_expected_command(self):
        expected = (
            "nohup ib_read_bw -d mlx5_1 -p 19001 -b --run_infinitely -D 1 -F 192.168.1.1 "
            "> /tmp/c.log 2>&1 &"
        )
        self.assertEqual(
            build_ib_read_bw_client_cmd("mlx5_1", 19001, "192.168.1.1", "/tmp/c.log"),
            expected,
        )


class TestBuildQueryCommands(unittest.TestCase):
    def test_builds_all_query_commands(self):
        expected = [
            "mlxconfig -d mlx5_0 q",
            "smpquery -C mlx5_0 pi 16 1",
            "perfquery -C mlx5_0 16 1",
            "ibportstate -C mlx5_0 16 1",
        ]
        self.assertEqual(build_query_commands("mlx5_0", "16"), expected)


if __name__ == "__main__":
    unittest.main()
