# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

#  type: ignore
"""
This script measures the failure rate of all wayflowcore flaky tests equipped
with the ``retry_test`` decorator, and compares the new performance with
the original test performance stored in the tests docstrings.
Finally, the script generates a HTML report to visualize the results.

The script can be executed as follows:

python run_flaky_analyzer.py \
    --submodules "wayflowcore" \
    --n-retries 50

Use `python run_flaky_analyzer.py -h` for more information.
"""

import argparse
import ast
import json
import logging
import math
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader


@dataclass
class FlakyTestStatistics:
    n_success: int
    n_failure: int
    total_time_success: Optional[float] = None
    total_time_failure: Optional[float] = None
    observation_date: Optional[datetime] = None

    @property
    def total_attempts(self) -> int:
        return self.n_failure + self.n_success

    @property
    def estimated_fail_rate(self) -> float:
        # We estimate the failure rate using Laplace Rule of Succession
        # See: https://en.wikipedia.org/wiki/Rule_of_succession
        # This makes the estimation of failure rate more robust. In particular
        # It does not estimate 100% success when we have 5 out of 5 successes
        return (self.n_failure + 1) / (self.n_failure + self.n_success + 2)

    @property
    def suggested_num_attempts(self) -> int:
        # We estimate the suggested number of attempts based on the objective
        # that we want strictly less than 1 in 10'000 expected failure. Thus giving
        # us the formula:
        #
        #     fail_rate ** N < 1/10'000
        #
        #  Which is transformed with a bit of mathematical magic into:
        #
        #     N > - log(10'000) / log(fail_rate)
        return math.ceil(-math.log(10_000) / math.log(self.estimated_fail_rate))

    @property
    def expected_failure_per_100_000(self) -> float:
        return 100_000 * (self.estimated_fail_rate**self.suggested_num_attempts)

    @property
    def average_success_time(self) -> Optional[float]:
        if self.n_success == 0 or self.total_time_success is None:
            return None
        return self.total_time_success / self.n_success

    @property
    def average_failure_time(self) -> Optional[float]:
        if self.n_failure == 0 or self.total_time_failure is None:
            return None
        return self.total_time_failure / self.n_failure


@dataclass
class TestResult:
    """
    Container combining previous and current test statistics.

    Parameters
    ----------
    test_id : str
        Unique identifier for the test (typically filepath::test_name)
    filepath : str
        Path to the test file
    test_name : str
        Name of the test function
    previous_stats : FlakyTestStatistics
        Statistics from the test's docstring
    current_stats : FlakyTestStatistics
        Statistics from the current test run
    log_file : str
        Path to the log file containing test output

    Attributes
    ----------
    failure_rate_change : float
        Change in failure rate (percentage points)
    has_degraded : bool
        Whether the failure rate has significantly increased
    """

    test_id: str
    filepath: str
    test_name: str
    previous_stats: FlakyTestStatistics
    current_stats: FlakyTestStatistics
    log_file: str

    @property
    def failure_rate_change(self) -> float:
        """Calculate change in failure rate (in percentage points)."""
        return self.current_stats.estimated_fail_rate - self.previous_stats.estimated_fail_rate

    @property
    def has_degraded(self) -> bool:
        """
        Determine if the test has significantly degraded.

        Uses a simple threshold of >5% increase in failure rate.
        Could be enhanced with statistical significance testing.
        """
        return self.failure_rate_change > 5.0


class TestingError(Exception):
    """Base exception for testing-related errors."""


class DocstringParseError(TestingError):
    """Raised when failing to parse test docstring."""


class TestExecutionError(TestingError):
    """Raised when test execution fails unexpectedly."""


def setup_logging(log_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Configure logging for the application.

    Parameters
    ----------
    log_dir : Union[str, Path]
        Directory where log files will be stored
    """
    log_dir = Path(log_dir) if log_dir else Path(__file__).parent
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_dir / "flake_analyzer.log"), logging.StreamHandler()],
    )


class FlakeAnalyzer:
    """
    Main class for analyzing flaky tests.

    This class handles test discovery, execution, and statistics collection
    for tests decorated with the retry_test decorator.
    """

    def __init__(
        self,
        repo_path: str,
        test_command_template: str,
        output_dir: str,
        n_retries: int,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.test_command_template = test_command_template
        self.output_dir = Path(output_dir)
        self.n_retries = n_retries

        self.logs_dir = self.output_dir / "logs"
        self.results_dir = self.output_dir / "results"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(__name__)

    def find_flaky_tests(self, folder_path: str) -> Dict[str, List[str]]:
        """
        Find all tests with retry decorator in the given folder.

        Parameters
        ----------
        folder_path : str
            Path to the folder containing test files

        Returns
        -------
        Dict[str, List[str]]
            Dictionary mapping file paths to lists of flaky test names

        Notes
        -----
        Uses AST parsing to find functions decorated with @retry_test
        """
        result = {}
        folder_path = Path(folder_path)

        for python_file in folder_path.rglob("*.py"):
            try:
                flaky_tests = self._find_flaky_tests_in_file(python_file)
                if flaky_tests:
                    result[str(python_file)] = flaky_tests
            except Exception as e:
                self.logger.error(f"Error processing {python_file}: {str(e)}")

        return result

    def _find_flaky_tests_in_file(self, filepath: Path) -> List[str]:
        """
        Find flaky tests in a single Python file.

        Parameters
        ----------
        filepath : Path
            Path to the Python file

        Returns
        -------
        List[str]
            List of flaky test names in the file
        """
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        flaky_tests = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and hasattr(node, "decorator_list")
                and any(self._is_retry_decorator(d) for d in node.decorator_list)
            ):
                flaky_tests.append(node.name)

        return flaky_tests

    def _is_retry_decorator(self, node: ast.AST) -> bool:
        """
        Check if an AST node is a retry_test decorator.

        Parameters
        ----------
        node : ast.AST
            AST node to check

        Returns
        -------
        bool
            True if node is a retry_test decorator
        """
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id == "retry_test"
        return False

    def extract_docstring_stats(self, filepath: str, test_name: str) -> FlakyTestStatistics:
        """
        Extract statistics from test docstring.

        Parameters
        ----------
        filepath : str
            Path to the test file
        test_name : str
            Name of the test function

        Returns
        -------
        FlakyTestStatistics
            Statistics parsed from the docstring

        Raises
        ------
        DocstringParseError
            If docstring cannot be parsed
        """
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == test_name
                and ast.get_docstring(node)
            ):
                return self._parse_docstring(ast.get_docstring(node))

        raise DocstringParseError(f"Could not find docstring for {test_name}")

    def _parse_docstring(self, docstring: str) -> FlakyTestStatistics:
        """
        Parse statistics from a test's docstring.

        Parameters
        ----------
        docstring : str
            The test's docstring

        Returns
        -------
        FlakyTestStatistics
            Parsed statistics

        Raises
        ------
        DocstringParseError
            If docstring format is invalid
        """
        try:
            failure_match = re.search(r"Failure rate:\s*(\d+)\s*out of\s*(\d+)", docstring)
            failures, total = map(int, failure_match.groups())
            successes = total - failures

            date_match = re.search(r"Observed on:\s*(\d{4}-\d{2}-\d{2})", docstring)
            observation_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")

            success_time_match = re.search(r"Average success time:\s*([\d.]+)", docstring)
            success_time = (
                float(success_time_match.group(1)) * successes if success_time_match else None
            )

            failure_time_match = re.search(r"Average failure time:\s*([\d.]+)", docstring)
            failure_time = (
                float(failure_time_match.group(1)) * failures if failure_time_match else None
            )

            return FlakyTestStatistics(
                n_success=successes,
                n_failure=failures,
                total_time_success=success_time,
                total_time_failure=failure_time,
                observation_date=observation_date,
            )

        except (AttributeError, ValueError) as e:
            raise DocstringParseError(f"Invalid docstring format: {str(e)}")

    def run_test_and_collect_stats(
        self, filepath: str, test_name: str
    ) -> Tuple[FlakyTestStatistics, str]:
        """
        Run test and collect statistics and logs.

        Parameters
        ----------
        filepath : str
            Path to the test file
        test_name : str
            Name of the test function

        Returns
        -------
        Tuple[FlakyTestStatistics, str]
            Tuple of (test statistics, log output)

        Raises
        ------
        TestExecutionError
            If test execution fails unexpectedly
        """
        command = self.test_command_template.format(
            filepath=filepath, test_name=test_name, n_retries=self.n_retries
        )
        try:
            result = subprocess.run(
                command.split(),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                env={**os.environ, "FLAKY_TEST_EVALUATION_MODE": str(self.n_retries)},
            )
            stats = self._filter_and_parse_output(result.stdout)
            return stats, result.stdout
        except subprocess.CalledProcessError as e:
            raise TestExecutionError(f"Test execution failed: {str(e)}")

    def _filter_and_parse_output(self, output: str) -> FlakyTestStatistics:
        """
        Parse test statistics from command output.

        Parameters
        ----------
        output : str
            Command output containing statistics

        Returns
        -------
        FlakyTestStatistics
            Parsed statistics
        """
        splitter = "Find below the recommended docstring and attempt count for your test"
        filtered_output = output.split(splitter)[-1][
            :300
        ]  # this filters to exactly what we need, i.e. the docstring
        if "Failure rate:" not in filtered_output:
            logging.warning("Skipped test parsing, check that output was not malformed: %s", output)
            return FlakyTestStatistics(
                n_success=0,
                n_failure=1,
                observation_date=datetime.now(),
            )
        return self._parse_docstring(filtered_output)

    def save_test_log(self, test_name: str, log_content: str) -> str:
        """
        Save test output to a log file.

        Parameters
        ----------
        test_name : str
            Name of the test
        log_content : str
            Content to save

        Returns
        -------
        str
            Path to the saved log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f"{test_name}_{timestamp}.log"

        with open(log_file, "w") as f:
            f.write(log_content)

        return str(log_file)

    def analyze_all_tests(self) -> List[TestResult]:
        """
        Analyze all flaky tests and collect results.

        Returns
        -------
        List[TestResult]
            List of test results with both previous and current statistics
        """
        results = []
        flaky_tests = self.find_flaky_tests(self.repo_path)
        for filepath, test_names in flaky_tests.items():
            for test_name in test_names:
                self.logger.info(f"Analyzing test: {filepath}::{test_name}")

                try:
                    previous_stats = self.extract_docstring_stats(filepath, test_name)
                    current_stats, log_output = self.run_test_and_collect_stats(filepath, test_name)

                    log_file = self.save_test_log(test_name, log_output)

                    result = TestResult(
                        test_id=f"{filepath}::{test_name}",
                        filepath=filepath,
                        test_name=test_name,
                        previous_stats=previous_stats,
                        current_stats=current_stats,
                        log_file=log_file,
                    )

                    results.append(result)

                except (DocstringParseError, TestExecutionError) as e:
                    self.logger.error(f"Error analyzing {test_name}: {str(e)}")
                    continue
        return results


class MultiModuleFlakeAnalyzer:
    def __init__(
        self,
        root_path: str,
        submodules: List[str],
        test_command_template: str,
        output_dir: str,
        n_retries: int,
    ) -> None:
        self.root_path = Path(root_path)
        self.submodules = submodules
        self.test_command_template = test_command_template
        self.output_dir = Path(output_dir)
        self.n_retries = n_retries
        self.analyzers: Dict[str, FlakeAnalyzer] = {}

        for submodule in submodules:
            submodule_path = self.root_path / submodule
            if not submodule_path.exists():
                raise ValueError(f"Submodule path does not exist: {submodule_path}")

            self.analyzers[submodule] = FlakeAnalyzer(
                repo_path=str(submodule_path),
                test_command_template=test_command_template,
                output_dir=str(self.output_dir / submodule),
                n_retries=n_retries,
            )

    def analyze_all(self) -> Dict[str, List[TestResult]]:
        results = {}
        for submodule, analyzer in self.analyzers.items():
            results[submodule] = analyzer.analyze_all_tests()
        return results

    def save_results(self, results: Dict[str, List[TestResult]]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"results_{timestamp}.json"

        serializable_results = {
            submodule: [
                {
                    "test_id": r.test_id,
                    "filepath": r.filepath,
                    "test_name": r.test_name,
                    "previous_stats": {
                        "failure_rate": r.previous_stats.estimated_fail_rate,
                        "observation_date": r.previous_stats.observation_date.isoformat(),
                        "success_time": r.previous_stats.average_success_time,
                        "failure_time": r.previous_stats.average_failure_time,
                    },
                    "current_stats": {
                        "failure_rate": r.current_stats.estimated_fail_rate,
                        "observation_date": r.current_stats.observation_date.isoformat(),
                        "success_time": r.current_stats.average_success_time,
                        "failure_time": r.current_stats.average_failure_time,
                    },
                    "log_file": r.log_file,
                }
                for r in submodule_results
            ]
            for submodule, submodule_results in results.items()
        }

        with open(output_file, "w") as f:
            json.dump(serializable_results, f, indent=2)

        return str(output_file)


class ReportGenerator:
    """
    Generates HTML report with test comparisons.

    Parameters
    ----------
    template_dir : str
        Directory containing HTML templates
    """

    def __init__(self, template_dir: str, repo_path: str):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.repo_path = repo_path
        self._current_commit_hash: Optional[str] = None

    @property
    def current_commit_hash(self) -> str:
        if self._current_commit_hash is not None:
            return self._current_commit_hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,  # Ensures the output is returned as a string
            )
            self._current_commit_hash = result.stdout.strip()[:11]
        except subprocess.CalledProcessError:
            logging.error("Failed to get the current commit hash")
            self._current_commit_hash = "unknown"
        return self._current_commit_hash

    def generate_failure_rate_chart(self, results: List[TestResult], submodule: str) -> str:
        """
        Generate failure rate comparison chart using plotly.

        Parameters
        ----------
        results : List[TestResult]
            Test results to visualize

        Returns
        -------
        str
            HTML div containing the chart
        """
        test_names = [r.test_name for r in results]
        previous_rates = [r.previous_stats.estimated_fail_rate for r in results]
        current_rates = [r.current_stats.estimated_fail_rate for r in results]

        fig = go.Figure(
            data=[
                go.Bar(name="Docstring", x=test_names, y=previous_rates),
                go.Bar(
                    name=f"Current at {self.current_commit_hash}", x=test_names, y=current_rates
                ),
            ]
        )

        fig.update_layout(
            title=f"Failure Rates - {submodule}",
            xaxis_title="Test Name",
            yaxis_title="Failure Rate (%)",
            barmode="group",
        )

        return fig.to_html(full_html=False)

    def generate_timing_scatter_plot(self, results: List[TestResult], submodule: str) -> str:
        """
        Generate timing comparison scatter plot.

        Parameters
        ----------
        results : List[TestResult]
            Test results to visualize

        Returns
        -------
        str
            HTML div containing the plot
        """
        test_names = [r.test_name for r in results]
        success_times_prev = [r.previous_stats.average_success_time for r in results]
        success_times_curr = [r.current_stats.average_success_time for r in results]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=test_names, y=success_times_prev, mode="markers", name="Success Time (Docstring)"
            )
        )
        fig.add_trace(
            go.Scatter(
                x=test_names,
                y=success_times_curr,
                mode="markers",
                name=f"Success Time (Current at {self.current_commit_hash})",
            )
        )
        fig.update_layout(
            title=f"Test Execution Times - {submodule}",
            xaxis_title="Test Name",
            yaxis_title="Time (seconds)",
        )
        return fig.to_html(full_html=False)

    def generate_html_report(self, results: Dict[str, List[TestResult]], output_path: str) -> None:
        """
        Generate final HTML report.

        Parameters
        ----------
        results : List[TestResult]
            Test results to include in report
        output_path : str
            Path where to save the HTML report
        """
        template = self.env.get_template("report_template.html")

        charts = {}
        for submodule, submodule_results in results.items():
            submodule_results.sort(key=lambda x: x.failure_rate_change, reverse=True)
            charts[submodule] = {
                "failure_rate": self.generate_failure_rate_chart(submodule_results, submodule),
                "timing": self.generate_timing_scatter_plot(submodule_results, submodule),
            }
        html_content = template.render(
            submodules=list(results.keys()),
            results=results,
            charts=charts,
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            commit_hash=self.current_commit_hash,
        )
        with open(output_path, "w") as f:
            f.write(html_content)


def get_current_repo_path() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(Path(__file__).parent),
        check=True,
        capture_output=True,
        text=True,  # Ensures the output is returned as a string
    )
    return result.stdout.strip()


def main():
    """Main execution function for the flaky test analyzer."""
    setup_logging()
    parser = argparse.ArgumentParser(description="Analyze flaky tests and generate report")
    DEFAULT_SUBMODULES = "wayflowcore"
    parser.add_argument(
        "--submodules",
        default=DEFAULT_SUBMODULES,
        help="Comma-separated list of submodule names to analyze",
    )
    parser.add_argument(
        "--test-command",
        default="python -m pytest {filepath}::{test_name}",
        help="Template for test command",
    )
    parser.add_argument(
        "--output-dir",
        default="./.flaky_tests_analysis",
        help="Output directory for results",
    )
    parser.add_argument("--n-retries", type=int, default=100, help="Number of test retries")

    args = parser.parse_args()
    repo_path = get_current_repo_path()

    submodules = [s.strip() for s in args.submodules.split(",")]

    analyzer = MultiModuleFlakeAnalyzer(
        root_path=repo_path,
        submodules=submodules,
        test_command_template=args.test_command,
        output_dir=args.output_dir,
        n_retries=args.n_retries,
    )
    results = analyzer.analyze_all()
    json_output = analyzer.save_results(results)
    logging.info("Raw results saved to: %s", json_output)

    template_dir = Path(__file__).parent / "templates"
    report_generator = ReportGenerator(
        template_dir=str(template_dir),
        repo_path=repo_path,
    )

    report_path = Path(args.output_dir) / "report.html"
    report_generator.generate_html_report(results, str(report_path))
    logging.info("HTML report generated: %s", report_path)


if __name__ == "__main__":
    main()
