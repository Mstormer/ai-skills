# Presentation Crafter

A Claude skill that turns a manuscript or outline into slide-by-slide content for PowerPoint or Keynote. It asks how many slides you want and how to divide the content, proposes a structure for your approval, then writes each slide's title and bullet points.

## Install

Copy this folder into `~/.claude/skills/` (Claude Code) or `~/.agents/skills/` (Codex), or upload it as a skill in Claude. Then say: "Create a presentation from my notes."

## Slide images

When you ask for an image for a slide, the skill uses an image tool if you have one connected, and otherwise writes an image prompt you can paste into any image generator.
