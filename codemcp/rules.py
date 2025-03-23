#!/usr/bin/env python3

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

from codemcp import glob

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
        frontmatter = {}
        for line in frontmatter_text.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                frontmatter[key] = value

        # Extract rule properties
        description = frontmatter.get("description")

        # Handle globs - can be comma-separated string or a list
        globs: List[str] = []
        globs_value = frontmatter.get("globs")
        if globs_value:
            globs = [g.strip() for g in globs_value.split(",")]

        # Convert alwaysApply string to boolean
        always_apply_value = frontmatter.get("alwaysApply", "false")
        always_apply = always_apply_value.lower() == "true"

        return Rule(
            description=description,
            globs=globs,
            always_apply=always_apply,
            payload=payload,
            file_path=file_path,
        )
    except Exception as e:
        # If there's any error parsing the file, return None
        print(f"Error loading rule from {file_path}: {e}")
        return None


def match_file_with_glob(file_path: str, glob_pattern: str) -> bool:
    """Check if a file path matches a glob pattern.

    Args:
        file_path: Path to check
        glob_pattern: Glob pattern to match against

    Returns:
        True if the file matches the pattern, False otherwise
    """
    # Convert to Path object for consistent handling
    path = Path(file_path)
    file_name = path.name

    logging.debug(
        f"match_file_with_glob: checking if '{file_path}' matches pattern '{glob_pattern}'"
    )

    # Simple case: direct file extension matching (*.js)
    # For compatibility with existing tests and code, we'll match *.js against any .js file
    # regardless of path, which matches the original behavior
    if glob_pattern.startswith("*."):
        result = file_name.endswith(glob_pattern[1:])
        logging.debug(
            f"Extension match (*.ext): pattern={glob_pattern}, file={file_name}, result={result}"
        )
        return result

    # Handle "**/*.js" pattern (match any file with .js extension in any directory)
    if glob_pattern.startswith("**/*."):
        ext = glob_pattern.split(".")[-1]
        result = file_name.endswith("." + ext)
        logging.debug(
            f"Any dir with extension (**/*.ext): pattern={glob_pattern}, ext=.{ext}, result={result}"
        )
        return result

    # Handle leading **/ patterns
    if glob_pattern.startswith("**/") and not "/**/" in glob_pattern:
        # **/file.txt - match file.txt in any directory
        simple_pattern = glob_pattern[3:]  # Remove leading **/

        # For simple filenames, just match the filename
        if "/" not in simple_pattern:
            result = file_name == simple_pattern
            logging.debug(
                f"Leading **/ with simple filename: pattern={simple_pattern}, file={file_name}, result={result}"
            )
            return result

    # Handle patterns like "src/**/*.jsx" (match files in src directory or subdirectories)
    if "/" in glob_pattern and "**" in glob_pattern:
        # Handle trailing /** (matches all files in a directory with infinite depth)
        if glob_pattern.endswith("/**"):
            dir_part = glob_pattern[:-3]  # Remove trailing "/**"
            logging.debug(f"Trailing ** pattern: dir_part='{dir_part}'")

            # Convert path to string for comparison
            path_str = str(path)

            # Check if dir_part is in the path (better matching than before)
            path_parts = path_str.split("/")
            result = dir_part in path_parts
            logging.debug(
                f"Directory match for trailing **: checking if '{dir_part}' is in path parts of '{path_str}', result={result}"
            )
            return result

        # Handle patterns with directory and file parts like "src/**/*.jsx"
        parts = glob_pattern.split("/**/")
        if len(parts) == 2:
            dir_part, file_part = parts
            logging.debug(
                f"Directory + file pattern: dir_part='{dir_part}', file_part='{file_part}'"
            )

            # Check if the file has the right extension
            if file_part.startswith("*"):
                ext = file_part[1:]  # *.jsx -> .jsx
                if not file_name.endswith(ext):
                    logging.debug(
                        f"Extension mismatch: expected '{ext}', file='{file_name}', result=False"
                    )
                    return False

            # Special case for patterns like src/**/Button.jsx
            if not file_part.startswith("*"):
                # For exact filename matches, compare directly
                result = dir_part in str(path) and file_name == file_part
                logging.debug(
                    f"Exact filename match: expected '{file_part}', got '{file_name}', result={result}"
                )
                return result

            # Check if it's in the right directory (as a path component)
            path_str = str(path)
            path_parts = path_str.split("/")
            result = dir_part in path_parts
            logging.debug(
                f"Directory match: checking if '{dir_part}' is in path parts '{path_parts}', result={result}"
            )
            return result

    # Handle question mark patterns with fnmatch
    if "?" in glob_pattern:
        import fnmatch

        result = fnmatch.fnmatch(file_name, glob_pattern)
        logging.debug(
            f"Question mark pattern match: pattern='{glob_pattern}', file='{file_name}', result={result}"
        )
        return result

    # Use the glob module for more complex patterns
    if "**" in glob_pattern:
        # For patterns with **, use the glob module
        result = glob.match(glob_pattern, str(path))
        logging.debug(
            f"Complex glob match: pattern='{glob_pattern}', path='{str(path)}', result={result}"
        )
        return result
    else:
        # For simple patterns without **, use fnmatch on the filename only
        import fnmatch

        result = fnmatch.fnmatch(file_name, glob_pattern)
        logging.debug(
            f"Simple fnmatch: pattern='{glob_pattern}', file='{file_name}', result={result}"
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
    logging.debug(
        f"Finding applicable rules for repo_root={repo_root}, file_path={file_path}"
    )

    # If file_path is provided, walk up from its directory to repo_root
    # Otherwise, just check repo_root
    start_dir = os.path.dirname(os.path.abspath(file_path)) if file_path else repo_root
    current_dir = start_dir
    logging.debug(f"Starting directory search at: {current_dir}")

    # Ensure we don't go beyond repo_root
    while current_dir.startswith(repo_root):
        # Look for .cursor/rules directory
        rules_dir = os.path.join(current_dir, ".cursor", "rules")
        logging.debug(f"Checking for rules directory: {rules_dir}")

        if os.path.isdir(rules_dir):
            logging.debug(f"Found rules directory: {rules_dir}")

            # Find all MDC files in this directory
            for root, _, files in os.walk(rules_dir):
                for filename in files:
                    if filename.endswith(".mdc"):
                        rule_file_path = os.path.join(root, filename)
                        logging.debug(f"Considering rule file: {rule_file_path}")

                        # Skip if we've already processed this file
                        if rule_file_path in processed_rule_files:
                            logging.debug(
                                f"Skipping already processed rule file: {rule_file_path}"
                            )
                            continue
                        processed_rule_files.add(rule_file_path)

                        # Load the rule
                        rule = load_rule_from_file(rule_file_path)
                        if rule is None:
                            logging.debug(
                                f"Failed to load rule from file: {rule_file_path}"
                            )
                            continue

                        # Check if this rule applies
                        if rule.always_apply:
                            logging.debug(f"Rule always applies: {rule_file_path}")
                            applicable_rules.append(rule)
                        elif file_path and rule.globs:
                            # Check if any glob pattern matches the file
                            logging.debug(
                                f"Checking glob patterns for rule: {rule_file_path}"
                            )
                            for glob_pattern in rule.globs:
                                logging.debug(
                                    f"Testing glob pattern: {glob_pattern} against file: {file_path}"
                                )
                                if match_file_with_glob(file_path, glob_pattern):
                                    logging.debug(
                                        f"Glob pattern matched: {glob_pattern}"
                                    )
                                    applicable_rules.append(rule)
                                    break
                                else:
                                    logging.debug(
                                        f"Glob pattern did not match: {glob_pattern}"
                                    )
                        elif rule.description:
                            # Add to suggested rules if it has a description
                            logging.debug(
                                f"Adding rule to suggested rules: {rule_file_path}"
                            )
                            suggested_rules.append((rule.description, rule_file_path))
                        else:
                            logging.debug(
                                f"Rule not applicable (no globs match or missing description): {rule_file_path}"
                            )

        # Move up one directory
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # We've reached the root
            logging.debug("Reached filesystem root, stopping directory traversal")
            break
        current_dir = parent_dir
        logging.debug(f"Moving up to parent directory: {current_dir}")

    logging.debug(
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
        logging.debug(
            f"get_applicable_rules_content called with repo_root={repo_root}, file_path={file_path}"
        )
        result = ""

        # Find applicable rules
        applicable_rules, suggested_rules = find_applicable_rules(repo_root, file_path)
        logging.debug(
            f"Retrieved {len(applicable_rules)} applicable rules and {len(suggested_rules)} suggested rules"
        )

        # If we have applicable rules, add them to the output
        if applicable_rules or suggested_rules:
            result += "\n\n// .cursor/rules results:"
            logging.debug("Adding rule results to output")

            # Add directly applicable rules
            for i, rule in enumerate(applicable_rules):
                rel_path = os.path.relpath(rule.file_path, repo_root)
                logging.debug(
                    f"Adding applicable rule {i + 1}/{len(applicable_rules)}: {rel_path}"
                )
                rule_content = f"\n\n// Rule from {rel_path}:\n{rule.payload}"
                result += rule_content

            # Add suggestions for rules with descriptions
            for i, (description, rule_path) in enumerate(suggested_rules):
                rel_path = os.path.relpath(rule_path, repo_root)
                logging.debug(
                    f"Adding suggested rule {i + 1}/{len(suggested_rules)}: {rel_path} ('{description}')"
                )
                result += f"\n\n// If {description} applies, load {rel_path}"
        else:
            logging.debug("No applicable or suggested rules found")

        logging.debug(f"Returning {len(result)} characters of rule content")
        return result
    except Exception as e:
        # Log the exception but don't propagate it
        logging.error(f"Error generating applicable rules content: {e}", exc_info=True)
        return ""
