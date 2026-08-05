import unittest
from app.agents.schemas import AgentState, AgentStatus
from app.agents.state_machine import AgentStateMachine, InvalidAgentStateTransitionError
from app.agents.manager import AgentManager
from app.agents.events import agent_event_bus, AgentEventType


class TestAgentPhase1(unittest.TestCase):

    def setUp(self):
        self.manager = AgentManager()

    def test_agent_creation_and_initial_state(self):
        status = self.manager.create_agent(goal_id="goal-101")
        self.assertEqual(status.state, AgentState.READY)
        self.assertEqual(status.goal_id, "goal-101")

    def test_state_machine_valid_transitions(self):
        status = self.manager.create_agent(goal_id="goal-102")
        self.assertEqual(status.state, AgentState.READY)

        # READY -> RUNNING
        self.manager.start_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.RUNNING)

        # RUNNING -> PAUSED
        self.manager.pause_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.PAUSED)

        # PAUSED -> RUNNING
        self.manager.resume_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.RUNNING)

        # RUNNING -> CANCELLED
        self.manager.cancel_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.CANCELLED)

    def test_state_machine_invalid_transition_rejection(self):
        status = self.manager.create_agent(goal_id="goal-103")
        # Agent is currently READY. Transitioning directly to COMPLETED (skipping RUNNING) must fail
        with self.assertRaises(InvalidAgentStateTransitionError):
            AgentStateMachine.transition(status, AgentState.COMPLETED)

    def test_agent_events(self):
        events = []
        agent_event_bus.subscribe(AgentEventType.AGENT_CREATED, lambda et, p: events.append((et, p)))
        agent_event_bus.subscribe(AgentEventType.AGENT_STARTED, lambda et, p: events.append((et, p)))

        status = self.manager.create_agent(goal_id="goal-104")
        self.manager.start_agent(status.agent_id)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0][0], AgentEventType.AGENT_CREATED.value)
        self.assertEqual(events[1][0], AgentEventType.AGENT_STARTED.value)


if __name__ == "__main__":
    unittest.main()
