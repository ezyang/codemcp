#!/usr/bin/env python3

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from codemcp.glob_pattern import match as glob_match

__all__ = [
    "Rule",
    "find_applicable_rules",
    "load_rule_from_file",
    "match_file_with_glob",
    "get_applicable_rules_content",
]


@dataclass
class Rule:
    """Represents a cursor rule loaded from an MDC file."""

    description: Optional[str]  # Description of when the rule is useful
    globs: List[str]  # List of glob patterns to match files
    always_apply: bool  # Whether the rule should always be applied
    payload: str  # The markdown content of the rule
    file_path: str  # Path to the MDC file


def load_rule_from_file(file_path: str) -> Optional[Rule]:
    """Load a rule from an MDC file.

    Args:
        file_path: Path to the MDC file

    Returns:
        A Rule object if the file is valid, None otherwise
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse the frontmatter and content
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
        if not frontmatter_match:
            return None

        frontmatter_text = frontmatter_match.group(1)
        payload = frontmatter_match.group(2).strip()

        # We need to manually parse the frontmatter to handle unquoted glob patterns
        frontmatter: Dict[str, str] = {}
        for line in frontmatter_text.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                frontmatter[key] = value

        # Extract rule properties
        description: Optional[str] = frontmatter.get("description")

        # Handle globs - can be comma-separated string or a list
        globs: List[str] = []
        globs_value: Optional[str] = frontmatter.get("globs")
        if globs_value:
            globs = [g.strip() for g in globs_value.split(",")]

        # Convert alwaysApply string to boolean
        always_apply_value: str = frontmatter.get("alwaysApply", "false")
        always_apply: bool = always_apply_value.lower() == "true"

        return Rule(
            description=description,
            globs=globs,
            always_apply=always_apply,
            payload=payload,
            file_path=file_path,
        )
    except Exception as e:
        # If there's any error parsing the file, return None
        logging.error(f"Error loading rule from {file_path}: {e}")
        return None


def match_file_with_glob(file_path: str, glob_pattern: str) -> bool:
    """Check if a file path matches a glob pattern.

    Args:
        file_path: Path to check
        glob_pattern: Glob pattern to match against

    Returns:
        True if the file matches the pattern, False otherwise
    """
    logging.info(
        f"match_file_with_glob: checking if '{file_path}' matches pattern '{glob_pattern}'"
    )

    # Normalize path for matching
    # Paths are normalized to use / for consistent matching across platforms
    path = Path(file_path)
    normalized_path = str(path).replace(os.sep, "/")

    # File paths must be relative, not absolute
    # (since glob patterns typically use relative paths)
    assert not os.path.isabs(normalized_path), (
        f"File path must be relative, got absolute path: {normalized_path}"
    )

    # For filename-only patterns (without path separators), we can match just the filename
    if "/" not in glob_pattern:
        file_name = path.name
        result = glob_match(glob_pattern, file_name)
        logging.info(
            f"Filename match: pattern='{glob_pattern}', file='{file_name}', result={result}"
        )
        return result

    # Use the glob matcher from glob.py for full path matching
    # Cursor rules use vanilla glob patterns (not editorconfig features)
    result = glob_match(glob_pattern, normalized_path)
    logging.info(
        f"Path match: pattern='{glob_pattern}', path='{normalized_path}', result={result}"
    )
    return result


def find_applicable_rules(
    repo_root: str, file_path: Optional[str] = None
) -> Tuple[List[Rule], List[Tuple[str, str]]]:
    """Find all applicable rules for the given file path.

    Walks up the directory tree from the file path to the repo root,
    looking for .cursor/rules directories and loading MDC files.

    Args:
        repo_root: Root of the repository
        file_path: Optional path to a file to match against rules

    Returns:
        A tuple containing (applicable_rules, suggested_rules)
        - applicable_rules: List of Rule objects that match the file
        - suggested_rules: List of (description, file_path) tuples for rules with descriptions
    """
    applicable_rules: List[Rule] = []
    suggested_rules: List[Tuple[str, str]] = []
    processed_rule_files: Set[str] = set()

    # Normalize paths
    repo_root = os.path.abspath(repo_root)
    logging.info(
        f"Finding applicable rules for repo_root={repo_root}, file_path={file_path}"
    )

    # If file_path is provided, walk up from its directory to repo_root
    # Otherwise, just check repo_root
    start_dir = os.path.dirname(os.path.abspath(file_path)) if file_path else repo_root
    current_dir = start_dir
    logging.info(f"Starting directory search at: {current_dir}")

    # Ensure we don't go beyond repo_root
    while current_dir.startswith(repo_root):
        # Look for .cursor/rules directory
        rules_dir = os.path.join(current_dir, ".cursor", "rules")
        logging.info(f"Checking for rules directory: {rules_dir}")

        if os.path.isdir(rules_dir):
            logging.info(f"Found rules directory: {rules_dir}")

            # Find all MDC files in this directory
            for root, _, files in os.walk(rules_dir):
                for filename in files:
                    if filename.endswith(".mdc"):
                        rule_file_path = os.path.join(root, filename)
                        logging.info(f"Considering rule file: {rule_file_path}")

                        # Skip if we've already processed this file
                        if rule_file_path in processed_rule_files:
                            logging.info(
                                f"Skipping already processed rule file: {rule_file_path}"
                            )
                            continue
                        processed_rule_files.add(rule_file_path)

                        # Load the rule
                        rule = load_rule_from_file(rule_file_path)
                        if rule is None:
                            logging.info(
                                f"Failed to load rule from file: {rule_file_path}"
                            )
                            continue

                        # Check if this rule applies
                        if rule.always_apply:
                            logging.info(f"Rule always applies: {rule_file_path}")
                            applicable_rules.append(rule)
                        elif file_path and rule.globs:
                            # Check if any glob pattern matches the file
                            logging.info(
                                f"Checking glob patterns for rule: {rule_file_path}"
                            )
                            for glob_pattern in rule.globs:
                                logging.info(
                                    f"Testing glob pattern: {glob_pattern} against file: {file_path}"
                                )
                                # Convert absolute path to relative path if needed
                                rel_file_path = file_path
                                if os.path.isabs(file_path):
                                    rel_file_path = os.path.relpath(
                                        file_path, repo_root
                                    )
                                    logging.info(
                                        f"Converting absolute path to relative: {file_path} → {rel_file_path}"
                                    )

                                if match_file_with_glob(rel_file_path, glob_pattern):
                                    logging.info(
                                        f"Glob pattern matched: {glob_pattern}"
                                    )
                                    applicable_rules.append(rule)
                                    break
                                else:
                                    logging.info(
                                        f"Glob pattern did not match: {glob_pattern}"
                                    )
                        elif rule.description:
                            # Add to suggested rules if it has a description
                            logging.info(
                                f"Adding rule to suggested rules: {rule_file_path}"
                            )
                            suggested_rules.append((rule.description, rule_file_path))
                        else:
                            logging.info(
                                f"Rule not applicable (no globs match or missing description): {rule_file_path}"
                            )

        # Move up one directory
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # We've reached the root
            logging.info("Reached filesystem root, stopping directory traversal")
            break
        current_dir = parent_dir
        logging.info(f"Moving up to parent directory: {current_dir}")

    logging.info(
        f"Found {len(applicable_rules)} applicable rules and {len(suggested_rules)} suggested rules"
    )
    return applicable_rules, suggested_rules


def get_applicable_rules_content(
    repo_root: str, file_path: Optional[str] = None
) -> str:
    """Generate a string with all applicable rules for a file or the current directory.

    This is a helper function used by multiple tools to format rule content
    in a consistent way.

    Args:
        repo_root: Root of the repository
        file_path: Optional path to a file to match against rules

    Returns:
        A formatted string containing all applicable rules, or an empty string if no rules apply
    """
    try:
        logging.info(
            f"get_applicable_rules_content called with repo_root={repo_root}, file_path={file_path}"
        )
        result = ""

        # Find applicable rules
        applicable_rules, suggested_rules = find_applicable_rules(repo_root, file_path)
        logging.info(
            f"Retrieved {len(applicable_rules)} applicable rules and {len(suggested_rules)} suggested rules"
        )

        # If we have applicable rules, add them to the output
        if applicable_rules or suggested_rules:
            result += "\n\n// .cursor/rules results:"
            logging.info("Adding rule results to output")

            # Add directly applicable rules
            for i, rule in enumerate(applicable_rules):
                rel_path = os.path.relpath(rule.file_path, repo_root)
                logging.info(
                    f"Adding applicable rule {i + 1}/{len(applicable_rules)}: {rel_path}"
                )
                rule_content = f"\n\n// Rule from {rel_path}:\n{rule.payload}"
                result += rule_content

            # Add suggestions for rules with descriptions
            for i, (description, rule_path) in enumerate(suggested_rules):
                rel_path = os.path.relpath(rule_path, repo_root)
                logging.info(
                    f"Adding suggested rule {i + 1}/{len(suggested_rules)}: {rel_path} ('{description}')"
                )
                result += f"\n\n// If {description} applies, load {rel_path}"
        else:
            logging.info("No applicable or suggested rules found")

        logging.info(f"Returning {len(result)} characters of rule content")
        return result
    except Exception as e:
        # Log the exception but don't propagate it
        logging.error(f"Error generating applicable rules content: {e}", exc_info=True)
        return ""
