# Code adapted from https://github.com/OpenDocCN/python-code-anls/blob/master/docs/hf-tfm/models----clvp----number_normalizer.py.md
# Below is the original copyright notice:
#
# coding=utf-8
# Copyright 2023 The HuggingFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""English Normalizer class for CLVP."""

import re


class EnglishNormalizer:
    def __init__(self):
        # List of (regular expression, replacement) pairs for abbreviations:
        self._abbreviations = [
            # Compile regular expressions for abbreviations and their replacements
            (re.compile("\\b%s\\." % x[0], re.IGNORECASE), x[1])
            for x in [
                ("mrs", "misess"),
                ("mr", "mister"),
                ("dr", "doctor"),
                ("st", "saint"),
                ("co", "company"),
                ("jr", "junior"),
                ("maj", "major"),
                ("gen", "general"),
                ("drs", "doctors"),
                ("rev", "reverend"),
                ("lt", "lieutenant"),
                ("hon", "honorable"),
                ("sgt", "sergeant"),
                ("capt", "captain"),
                ("esq", "esquire"),
                ("ltd", "limited"),
                ("col", "colonel"),
                ("ft", "fort"),
            ]
        ]

        # List of English words for numbers
        self.ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        self.teens = [
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
        self.tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    def number_to_words(self, num: int) -> str:
        """
        Converts numbers(`int`) to words(`str`).

        Please note that it only supports up to - "'nine hundred ninety-nine quadrillion, nine hundred ninety-nine
        trillion, nine hundred ninety-nine billion, nine hundred ninety-nine million, nine hundred ninety-nine
        thousand, nine hundred ninety-nine'" or `number_to_words(999_999_999_999_999_999)`.
        """
        # If input number is 0, return "zero"
        if num == 0:
            return "zero"
        # If input number is negative, return minus representation and recursively call for absolute value
        elif num < 0:
            return "minus " + self.number_to_words(abs(num))
        # Handle numbers from 0 to 9, returning corresponding word
        elif num < 10:
            return self.ones[num]
        # Handle numbers from 10 to 19, returning corresponding word
        elif num < 20:
            return self.teens[num - 10]
        # Handle numbers from 20 to 99, split into tens and units, recursively handling units
        elif num < 100:
            return self.tens[num // 10] + ("-" + self.number_to_words(num % 10) if num % 10 != 0 else "")
        # Handle numbers from 100 to 999, split into hundreds and remainder, recursively handling remainder
        elif num < 1000:
            return (
                    self.ones[num // 100] + " hundred" + (
                " " + self.number_to_words(num % 100) if num % 100 != 0 else "")
            )
        # Handle numbers from 1,000 to 999,999, split into thousands and remainder, recursively handling remainder
        elif num < 1_000_000:
            return (
                    self.number_to_words(num // 1000)
                    + " thousand"
                    + (", " + self.number_to_words(num % 1000) if num % 1000 != 0 else "")
            )
        # Handle numbers from 1,000,000 to 999,999,999, split into millions and remainder, recursively handling remainder
        elif num < 1_000_000_000:
            return (
                    self.number_to_words(num // 1_000_000)
                    + " million"
                    + (", " + self.number_to_words(num % 1_000_000) if num % 1_000_000 != 0 else "")
            )
        # Handle numbers from 1,000,000,000 to 999,999,999,999, split into billions and remainder, recursively handling remainder
        elif num < 1_000_000_000_000:
            return (
                    self.number_to_words(num // 1_000_000_000)
                    + " billion"
                    + (", " + self.number_to_words(num % 1_000_000_000) if num % 1_000_000_000 != 0 else "")
            )
        # Handle numbers from 1,000,000,000,000 to 999,999,999,999,999, split into trillions and remainder, recursively handling remainder
        elif num < 1_000_000_000_000_000:
            return (
                    self.number_to_words(num // 1_000_000_000_000)
                    + " trillion"
                    + (", " + self.number_to_words(num % 1_000_000_000_000) if num % 1_000_000_000_000 != 0 else "")
            )
        # Handle numbers from 10^15 to 10^18 - 1, split into quadrillions and remainder, recursively handling remainder
        elif num < 1_000_000_000_000_000_000:
            return (
                    self.number_to_words(num // 1_000_000_000_000_000)
                    + " quadrillion"
                    + (
                        ", " + self.number_to_words(num % 1_000_000_000_000_000)
                        if num % 1_000_000_000_000_000 != 0
                        else ""
                    )
            )
        # Numbers out of range
        else:
            return "number out of range"

    def convert_to_ascii(self, text: str) -> str:
        """
        Converts unicode to ascii
        """
        # Convert Unicode text to ASCII encoding, ignoring non-ASCII characters
        return text.encode("ascii", "ignore").decode("utf-8")

    def _expand_dollars(self, m: str) -> str:
        """
        This method is used to expand numerical dollar values into spoken words.
        """
        # Matched numeric string (currency value)
        match = m.group(1)
        # Split currency value by decimal point into integer and fractional parts
        parts = match.split(".")
        if len(parts) > 2:
            return match + " dollars"  # If more than one decimal point, return raw string plus " dollars"

        # Parse integer and fractional parts
        dollars = int(parts[0]) if parts[0] else 0
        cents = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        # Construct spoken English representation based on integer and fractional parts
        if dollars and cents:
            dollar_unit = "dollar" if dollars == 1 else "dollars"
            cent_unit = "cent" if cents == 1 else "cents"
            return "%s %s, %s %s" % (dollars, dollar_unit, cents, cent_unit)
        elif dollars:
            dollar_unit = "dollar" if dollars == 1 else "dollars"
            return "%s %s" % (dollars, dollar_unit)
        elif cents:
            cent_unit = "cent" if cents == 1 else "cents"
            return "%s %s" % (cents, cent_unit)
        else:
            return "zero dollars"

    def _remove_commas(self, m: str) -> str:
        """
        This method is used to remove commas from sentences.
        """
        # Remove commas from input string
        return m.group(1).replace(",", "")

    def _expand_decimal_point(self, m: str) -> str:
        """
        This method is used to expand '.' into spoken word ' point '.
        """
        # Replace '.' in input string with word " point "
        return m.group(1).replace(".", " point ")

    def _expand_ordinal(self, num: str) -> str:
        """
        This method is used to expand ordinals such as '1st', '2nd' into spoken words.
        """
        # Ordinal suffix mapping
        ordinal_suffixes = {1: "st", 2: "nd", 3: "rd"}

        # Extract numeric part of ordinal and convert to integer
        num = int(num.group(0)[:-2])
        # Select appropriate suffix based on ordinal value
        if 10 <= num % 100 <= 20:
            suffix = "th"
        else:
            suffix = ordinal_suffixes.get(num % 10, "th")
        # Convert integer to English words and append ordinal suffix
        return self.number_to_words(num) + suffix

    def _expand_number(self, m: str) -> str:
        """
        This method acts as a preprocessing step for numbers between 1000 and 3000 (same as the original repository,
        link :
        https://github.com/neonbjb/tortoise-tts/blob/4003544b6ff4b68c09856e04d3eff9da26d023c2/tortoise/utils/tokenizer.py#L86)
        """
        # Extract matched number string and convert to integer
        num = int(m.group(0))

        # If number is between 1000 and 3000, expand according to specific spoken English rules
        if 1000 < num < 3000:
            if num == 2000:
                return "two thousand"
            elif 2000 < num < 2010:
                return "two thousand " + self.number_to_words(num % 100)
            elif num % 100 == 0:
                return self.number_to_words(num // 100) + " hundred"
            else:
                return self.number_to_words(num)
        else:
            return self.number_to_words(num)

    # Normalize numbers in text (convert digits to words, remove commas, etc.)
    def normalize_numbers(self, text: str) -> str:
        # Remove commas from numbers by calling self._remove_commas
        text = re.sub(re.compile(r"([0-9][0-9\,]+[0-9])"), self._remove_commas, text)
        # Expand pound amounts into word form
        text = re.sub(re.compile(r"£([0-9\,]*[0-9]+)"), r"\1 pounds", text)
        # Expand dollar amounts by calling self._expand_dollars
        text = re.sub(re.compile(r"\$([0-9\.\,]*[0-9]+)"), self._expand_dollars, text)
        # Expand decimals by calling self._expand_decimal_point
        text = re.sub(re.compile(r"([0-9]+\.[0-9]+)"), self._expand_decimal_point, text)
        # Expand ordinals (e.g. 1st, 2nd) by calling self._expand_ordinal
        text = re.sub(re.compile(r"[0-9]+(st|nd|rd|th)"), self._expand_ordinal, text)
        # Expand remaining numbers by calling self._expand_number
        text = re.sub(re.compile(r"[0-9]+"), self._expand_number, text)
        # Return normalized text
        return text

    # Expand abbreviations
    def expand_abbreviations(self, text: str) -> str:
        # Iterate through abbreviation patterns and substitute them
        for regex, replacement in self._abbreviations:
            text = re.sub(regex, replacement, text)
        # Return expanded text
        return text

    # Collapse whitespace
    def collapse_whitespace(self, text: str) -> str:
        # Replace consecutive whitespace characters with a single space
        return re.sub(re.compile(r"\s+"), " ", text)

    # Callable method: convert text to ASCII, expand numbers, and expand abbreviations
    def __call__(self, text):
        # Convert text to ASCII
        text = self.convert_to_ascii(text)
        # Convert text to lowercase
        text = text.lower()
        # Normalize numbers in text
        text = self.normalize_numbers(text)
        # Expand abbreviations in text
        text = self.expand_abbreviations(text)
        # Collapse whitespace in text
        text = self.collapse_whitespace(text)
        # Remove double quotation marks
        text = text.replace('"', "")

        # Return processed text
        return text
