from activfinancial import *
from activfinancial.constants import *


def topic_status_message_to_string(msg):
    output = (
        f"{format_message_field('DataSource',             msg.data_source_id)}"
        f"{format_message_field('Symbology',              msg.symbology_id)}"
        f"{format_message_field('Symbol',                 msg.symbol)}"
        f"{format_message_field('TopicSubscriptionState', topic_subscription_state_to_string(msg.topic_subscription_state))}"
    )

    return output


def format_message_field(name, field):
    NAME_WIDTH = 40
    filler = "." * (NAME_WIDTH - len(name[: NAME_WIDTH - 1]))

    if isinstance(field, Field):
        if field.is_defined():
            string = str(field)
        else:
            string = "undefined"

        if not field.does_update_last:
            string += " *"
    elif field is None:
        return ""
    else:
        string = str(field)

    return f"{name} {filler} {string}\n"
