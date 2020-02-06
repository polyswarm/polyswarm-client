import logging
from datetime import datetime
from pythonjsonlogger import jsonlogger


class ExtraTextFormatter(logging.Formatter):
    """
    Custom formatter that adds extra fields to the message string
    """

    def format(self, record):
        """
        Takes a LogRecord and sets record.message = record.msg % record.args
        This one does some extra work.
        It searches the record dict for some extra keys we use in the client. (specified as extra= in the logger statement)
        If it finds one, it grabs the dict and adds an extra %s arg to record.msg, and the dict value to the record.args tuple.
        """
        # search for extra keys in the dict.
        extra = record.__dict__.get('extra')
        if extra is not None:
            # Add the extra value to the msg format string and the dict to the tuple
            record.msg += ': %s'
            # add extra dict as a tuple
            record.args = record.args + (extra,)

        return super().format(record)


class JSONFormatter(jsonlogger.JsonFormatter):
    """
    Class to add custom JSON fields to our logger.
    Presently just adds a timestamp if one isn't present and the log level.
    INFO: https://github.com/madzak/python-json-logger#customizing-fields
    """

    def add_fields(self, log_record, record, message_dict):
        super(JSONFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            # this doesn't use record.created, so it is slightly off
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
