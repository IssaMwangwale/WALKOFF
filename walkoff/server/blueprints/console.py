import quart.flask_patch

import logging
from uuid import UUID

from quart import request
from quart_openapi import Resource
from flask_jwt_extended import jwt_required

from http import HTTPStatus

import walkoff.config
from walkoff.helpers import load_yaml
from walkoff.events import WalkoffEvent
from walkoff.server.problem import Problem
from walkoff.server.returncodes import BAD_REQUEST
from walkoff.sse import FilteredSseStream, StreamableBlueprint

console_stream = FilteredSseStream('console_results')
console_page = StreamableBlueprint('console_page', __name__, streams=(console_stream,))


def format_console_data(sender, data):
    try:
        level = int(data['level'])
    except ValueError:
        level = data['level']
    return {
        'workflow': sender['name'],
        'app_name': data['app_name'],
        'action_name': data['action_name'],
        'level': logging.getLevelName(level),
        'message': data['message']
    }


@WalkoffEvent.ConsoleLog.connect
@console_stream.push('log')
def console_log_callback(sender, **kwargs):
    return format_console_data(sender, kwargs["data"]), sender['execution_id']


@console_page.route('/log')
class StreamConsoleEvents(Resource):
    @jwt_required
    @console_page.param("workflow_execution_id",
                        console_page.create_ref_validator("workflow_execution_id", "parameters"))
    @console_page.response(HTTPStatus.OK, "Success")  # TODO: Schema for returned SSE
    def get(self):
        workflow_execution_id = request.args.get('workflow_execution_id')
        if workflow_execution_id is None:
            return Problem(
                BAD_REQUEST,
                'Could not connect to log stream',
                'workflow_execution_id is a required query param')
        try:
            UUID(workflow_execution_id)
            return console_stream.stream(subchannel=workflow_execution_id)
        except (ValueError, AttributeError):
            return Problem(
                BAD_REQUEST,
                'Could not connect to log stream',
                'workflow_execution_id must be a valid UUID')
