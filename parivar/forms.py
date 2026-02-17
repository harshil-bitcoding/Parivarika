from django import forms
from django.core.exceptions import ValidationError
from .models import Person
import re
from django.core.exceptions import ValidationError


def validate_single_emoji(value):
    emoji_pattern = re.compile(
        "^[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U00002B50"
        "\U00002B55"
        "\U000023E9-\U000023EF"
        "\U0001F004"
        "\U0001F0CF"
        "]+$",
        flags=re.UNICODE,
    )

    if not emoji_pattern.fullmatch(value):
        raise ValidationError("Please enter a valid single emoji.")

    if len(value) > 1 and value.count("\u200D") + value.count("\uFE0F") == 0:
        raise ValidationError("Only one emoji is allowed.")


class PersonForm(forms.ModelForm):

    emoji = forms.CharField(
        max_length=2,
        required=False,
        validators=[validate_single_emoji],
        widget=forms.TextInput(attrs={"size": "4"}),  # Adjust the size here
    )

    class Meta:
        model = Person
        fields = "__all__"
