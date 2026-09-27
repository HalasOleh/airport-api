"""Rebuild the vector index for the bot's knowledge base."""
import logging

from django.core.management.base import BaseCommand

from ai_bot.rag.indexer import reindex_all

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Embed the knowledge base files and reference tables into pgvector."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-embed every source even when its checksum is unchanged.",
        )

    def handle(self, *args, **options):
        report = reindex_all(force=options["force"])

        # self.stdout is the command's own output channel, not debug printing:
        # a human ran this and is waiting to see what happened. The mechanics
        # of the run are logged separately inside the indexer.
        for entry in report:
            status = entry["status"]
            if status == "error":
                self.stdout.write(self.style.WARNING(
                    f"{entry['source']}: skipped - {entry['detail']}"
                ))
            elif status == "unchanged":
                self.stdout.write(f"{entry['source']}: unchanged ({entry['chunks']} chunks)")
            elif status == "removed":
                self.stdout.write(self.style.WARNING(
                    f"{entry['source']}: retired - row and chunks deleted"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"{entry['source']}: indexed {entry['chunks']} chunks"
                ))

        indexed = sum(e.get("chunks", 0) for e in report if e["status"] != "error")
        self.stdout.write(f"Knowledge base holds {indexed} chunks.")
