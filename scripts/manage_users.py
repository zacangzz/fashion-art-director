#!/usr/bin/env python3
"""
CLI Utility for Managing Fashion AI Studio Whitelist and Admin Users.

Usage:
  uv run python scripts/manage_users.py list
  uv run python scripts/manage_users.py add --email user@example.com --role admin --status approved
  uv run python scripts/manage_users.py update --email user@example.com --role admin --status approved
  uv run python scripts/manage_users.py remove --email user@example.com
"""

import sys
import os
import argparse
from datetime import datetime, timezone

# Ensure src is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from google.cloud import firestore
from app.config import get_settings


def get_db():
    settings = get_settings()
    return firestore.Client(project=settings.GCP_PROJECT_ID)


def list_users():
    db = get_db()
    docs = list(db.collection("users").stream())
    if not docs:
        print("No users found in database.")
        return

    print(f"\n{'ID':<35} {'EMAIL':<30} {'ROLE':<10} {'STATUS':<15} {'SPEND ($)':<10}")
    print("=" * 105)
    for d in docs:
        data = d.to_dict()
        user_id = str(data.get("id") or d.id)[:33]
        email = str(data.get("email", "N/A"))[:28]
        role = str(data.get("role", "user"))[:8]
        status = str(data.get("status", "pending"))[:13]
        spend = f"${data.get('total_spend_usd', 0.0):.2f}"
        print(f"{user_id:<35} {email:<30} {role:<10} {status:<15} {spend:<10}")
    print()


def add_or_update_user(email: str, role: str = "user", status: str = "approved"):
    db = get_db()
    norm_email = email.strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()

    docs = list(db.collection("users").where("email", "==", norm_email).stream())
    if docs:
        for d in docs:
            db.collection("users").document(d.id).set({
                "role": role,
                "status": status,
                "approved_at": now_iso if status == "approved" else None,
            }, merge=True)
            print(f"Updated existing user '{d.id}' ({norm_email}) -> role={role}, status={status}.")
    else:
        invite_id = f"invite_{norm_email}"
        doc_data = {
            "id": invite_id,
            "email": norm_email,
            "display_name": norm_email.split("@")[0],
            "photo_url": None,
            "role": role,
            "status": status,
            "invited_by": "cli_admin",
            "created_at": now_iso,
            "approved_at": now_iso if status == "approved" else None,
            "last_login_at": None,
            "total_spend_usd": 0.0,
            "total_tokens": 0,
        }
        db.collection("users").document(invite_id).set(doc_data)
        print(f"Created new user record '{invite_id}' ({norm_email}) -> role={role}, status={status}.")


def remove_user(email: str):
    db = get_db()
    norm_email = email.strip().lower()
    docs = list(db.collection("users").where("email", "==", norm_email).stream())
    if not docs:
        print(f"No user found with email '{norm_email}'.")
        return

    for d in docs:
        db.collection("users").document(d.id).delete()
        print(f"Removed user document '{d.id}' ({norm_email}) from Firestore.")


def main():
    parser = argparse.ArgumentParser(description="Manage Fashion AI Studio Users & Whitelist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all studio users and whitelist entries")

    # add / update
    add_parser = subparsers.add_parser("add", help="Add or pre-authorize a user email")
    add_parser.add_argument("--email", required=True, help="User email address")
    add_parser.add_argument("--role", default="user", choices=["admin", "user"], help="User role")
    add_parser.add_argument("--status", default="approved", choices=["approved", "pending_invite", "disabled"], help="Approval status")

    update_parser = subparsers.add_parser("update", help="Update a user's role or status")
    update_parser.add_argument("--email", required=True, help="User email address")
    update_parser.add_argument("--role", default="user", choices=["admin", "user"], help="User role")
    update_parser.add_argument("--status", default="approved", choices=["approved", "pending_invite", "disabled"], help="Approval status")

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove a user from whitelist")
    remove_parser.add_argument("--email", required=True, help="User email address")

    args = parser.parse_args()

    if args.command == "list":
        list_users()
    elif args.command in ("add", "update"):
        add_or_update_user(args.email, args.role, args.status)
    elif args.command == "remove":
        remove_user(args.email)


if __name__ == "__main__":
    main()
