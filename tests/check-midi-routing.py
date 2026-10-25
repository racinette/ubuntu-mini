#!/usr/bin/env python3
"""Check that identical JACK client names cannot redirect controller input."""
import importlib.machinery
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('mapper_midi', str(PROJECT/'setup/desktop/minion-gamepad'))
spec = importlib.util.spec_from_loader(loader.name, loader)
mapper = importlib.util.module_from_spec(spec)
loader.exec_module(mapper)


def fixture(pid, client, node, port, direction, name):
    return [
        {'id':client, 'type':'PipeWire:Interface:Client', 'info':{'props':{
            'client.name':'REAPER','pipewire.sec.pid':pid,'application.process.id':999}}},
        {'id':node, 'type':'PipeWire:Interface:Node', 'info':{'props':{'client.id':str(client)}}},
        {'id':port, 'type':'PipeWire:Interface:Port', 'info':{'props':{
            'node.id':str(node),'port.name':name,'port.direction':direction,'format.dsp':'8 bit raw midi'}}}
    ]


graph = fixture(123,1,2,3,'in','MIDI Input 1') + fixture(456,4,5,6,'in','MIDI Input 1')
graph += fixture(789,7,8,9,'out','Controls')
assert mapper.pipewire_midi_ports(graph,123,'in') == [(3,'MIDI Input 1')]
assert mapper.pipewire_midi_ports(graph,456,'in') == [(6,'MIDI Input 1')]
assert mapper.pipewire_midi_ports(graph,999,'in') == []
assert mapper.pipewire_midi_ports(graph,123,'out') == []
connection = object.__new__(mapper.ReaperMidi)
connection.input_index = 0
connection.jack_output = Mock()
connection.jack_route = None
with patch.object(mapper.os,'getpid',return_value=789), patch.object(mapper.subprocess,'run') as command:
    assert not connection.connect_jack(999,graph)
    assert not command.called
    assert connection.connect_jack(123,graph)
    assert command.call_args.args[0] == ['pw-link','9','3']
    assert connection.backend == 'jack'
    command.reset_mock()
    linked = graph + [{'id':10,'type':'PipeWire:Interface:Link','info':{'output-port-id':9,'input-port-id':3}}]
    assert connection.connect_jack(123,linked)
    assert not command.called
    # A reset may reuse IDs but destroy the link. Reconnect even in that case.
    assert connection.connect_jack(123,graph)
    assert command.call_args.args[0] == ['pw-link','9','3']
    command.reset_mock()
    assert connection.connect_jack(456,graph)
    assert [call.args[0] for call in command.call_args_list] == [['pw-link','-d','9','3'],['pw-link','9','6']]
print('Passed: JACK routing by authenticated PID, duplicate client names, controller input selection, retained links, reset recovery and explicit rerouting.')
