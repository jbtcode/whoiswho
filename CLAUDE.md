# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Who Is Who** is an internal gamified web application for employee onboarding. It lets employees discover and get to know their colleagues through profile pages, search, and mini-games.

## Current State

This repository is in early planning/skeleton phase. No source code, build system, package manager, or tooling has been set up yet. The `docs/data-design.md` is a placeholder for the data architecture.

## Planned Architecture

- **Hosting**: Azure Web App
- **Auth**: SSO
- **Storage**: Azure Storage Account + Azure Table Storage (NoSQL-style, schema-flexible per profile)
- **CI/CD**: Azure DevOps
- **External integrations**:
  - **TeamTailor** — pre-populates profiles for new hires before their start date
  - **WHOZ** — professional skills/project history
  - **Odoo** — HR data
  - **Unit4** — HR/finance data
  - **Microsoft Teams / Viva Engage** — communications

## Data Model Principles

- Each person has a profile combining professional data (from integrations) and personal data (self-submitted only).
- Data policy: only use professionally-sourced data or data the individual explicitly submitted themselves.
- Storage should be NoSQL-like to accommodate evolving profile fields and new data types without schema migrations.

## Key Features to Build

- **Profile page** — view/edit personal and professional info (picture, manager, hobbies, etc.)
- **Search** — phonetic/soundex name search; characteristic-based search (appearance, hobbies, skills via WHOZ)
- **New joiners / leavers** — list of recent arrivals and departures
- **Quiz / mini-games** — true/false questions, face-to-name matching, pet-to-owner matching; extensible to new game types
- **Extensible page system** — adding new pages/modules/mini-games should require minimal boilerplate
