#!/usr/bin/env python3
"""Render git commit messages from workflow-config templates."""

from __future__ import annotations


def render_commit_message(
    template: str,
    *,
    task_id: str,
    scope: str = "code",
    summary: str = "",
) -> str:
    """Substitute {scope}, {task_id}, {summary} in commit_message_template."""
    return (
        template.replace("{scope}", scope)
        .replace("{task_id}", task_id)
        .replace("{summary}", summary)
        .replace("{subject}", summary)
    )
