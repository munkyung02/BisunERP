from __future__ import annotations

import json
from pathlib import Path


class MappingLearner:

    def __init__(self):

        self.file = (
            Path(__file__).parent /
            "mapping_history.json"
        )

        self.rules = {}

        self.load()

    def load(self):

        if self.file.exists():

            try:

                self.rules = json.loads(
                    self.file.read_text(
                        encoding="utf-8"
                    )
                )

            except Exception:

                self.rules = {}

    def save(self):

        self.file.write_text(

            json.dumps(

                self.rules,

                ensure_ascii=False,

                indent=4

            ),

            encoding="utf-8"

        )

    def learn(

        self,

        platform_name,

        product_id

    ):

        key = platform_name.strip().lower()

        self.rules[key] = product_id

        self.save()

    def predict(

        self,

        platform_name

    ):

        return self.rules.get(

            platform_name.strip().lower()

        )