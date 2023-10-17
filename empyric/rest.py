from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import os
from empyric.types import recast


class RESTapi:
    def __init__(self, instruments):
        ''''''
        self._instruments = instruments
        self._url_prefix = '/api/v1'
        self._thread: threading.Thread = None
        self._app = Flask(__name__)
        CORS(self._app)
        self._app.add_url_rule(self._url_prefix+'/instruments', view_func=self.list_instruments, methods=['GET'])
        self._app.add_url_rule(self._url_prefix+'/instruments/<string:name>', view_func=self.interact, methods=['GET', 'PUT'])
        self._app.add_url_rule(self._url_prefix+'/instruments/<string:name>/knobs/grafana-config', view_func=self.get_grafana_config, methods=['GET'])

    def list_instruments(self):
        ''''''
        return jsonify([instrument.name.replace(' ', '_') for instrument in self._instruments.values()])

    def interact(self, name: str = None):
        target_instrument = self.get_instrument_by_name(name.replace('_', ' '))
        if target_instrument is not None:
            if request.method == 'PUT':
                # modify values
                print(request.json)
                for knob in request.json:
                    try:
                        target_instrument.set(knob.replace(' ', '_'), recast(request.json[knob]))
                    except AttributeError:
                        pass

            # return values in either GET or PUT case
            values = {}
            for knob in target_instrument.knobs:
                values.update({knob: getattr(target_instrument, knob.replace(' ', '_'))})
            for meter in target_instrument.meters:
                values.update({meter: getattr(target_instrument, meter.replace(' ', '_'))})
            return jsonify(values)
        else:
            return 'Unrecognized instrument name.'

    def get_grafana_config(self, name: str):
        ''''''
        target_instrument = self.get_instrument_by_name(name.replace('_', ' '))
        if target_instrument is not None:
            resp = []
            for knob in target_instrument.knobs:
                resp.append({'id': knob,
                             'title': knob,
                             'type': 'number', #TODO this should be dynamic
                             'value': str(getattr(target_instrument, knob.replace(' ', '_'))),
                             'unit': ''})
            return jsonify(resp)

    def get_instrument_by_name(self, name):
        ''''''
        for instrument in self._instruments.values():
            if instrument.name == name:
                return instrument
        # no instrument found
        return None

    def run(self):
        ''''''
        # Need to start thread and have some logic to see if thread is already running
        print('Starting REST API')
        #self._app.run()
        self._thread = threading.Thread(target=lambda: self._app.run(use_reloader=False), daemon=True)
        self._thread.start()
        print('REST API started')

    def stop(self):
        ''''''
        if self._thread is not None:
            func = os.environ.get('werkzeug.server.shutdown')
            func()
            self._thread.join()
