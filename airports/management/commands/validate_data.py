"""Run every model's own validators over the rows already in the database.

Validators declared on a model only fire when something calls full_clean().
Serializers and ModelForms do; objects.create(), bulk_create(), loaddata and
raw SQL do not. So a table can quietly fill up with rows its own model would
reject - which is exactly what happened here.
"""
import logging

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

DEFAULT_APPS = ("airports", "tickets", "ai_bot")


class Command(BaseCommand):
    help = "Report rows that violate their own model validators."

    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            action="append",
            dest="app_labels",
            help="App label to check; repeatable. Defaults to airports, tickets, ai_bot.",
        )
        parser.add_argument(
            "--max-rows",
            type=int,
            default=5,
            help="How many offending rows to print per model. 0 prints all.",
        )
        parser.add_argument(
            "--fail",
            action="store_true",
            help="Exit non-zero when anything is invalid, for use in CI.",
        )

    def handle(self, *args, **options):
        app_labels = options["app_labels"] or list(DEFAULT_APPS)
        total_bad = 0

        for label in app_labels:
            for model in apps.get_app_config(label).get_models():
                bad = []
                for obj in model.objects.all():
                    try:
                        obj.full_clean()
                    except ValidationError as exc:
                        bad.append((obj.pk, str(obj), exc.message_dict))

                total_bad += len(bad)
                header = f"{label}.{model.__name__}: {model.objects.count()} rows"
                if not bad:
                    self.stdout.write(self.style.SUCCESS(f"{header}, all valid"))
                    continue

                self.stdout.write(self.style.WARNING(f"{header}, {len(bad)} invalid"))

                limit = options["max_rows"] or len(bad)
                for pk, label_text, errors in bad[:limit]:
                    for field, messages in errors.items():
                        self.stdout.write(
                            f"    id={pk} {label_text!r} -> {field}: {messages[0]}"
                        )
                if len(bad) > limit:
                    self.stdout.write(f"    ... and {len(bad) - limit} more")

        if total_bad and options["fail"]:
            raise SystemExit(1)

        self.stdout.write(f"\n{total_bad} invalid row(s) in total.")
