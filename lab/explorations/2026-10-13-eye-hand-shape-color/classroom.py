"""Declared classroom operations. Teacher truth is separate from the executor."""
import itertools
import time

import numpy as np
from system import window

from lab.tools.eye_hand_world import teacher_eye_angle

DT = .05
TICKS = 120
QUESTION_TICKS = 40
DECISION_TICKS = 10


def project(observation, xyz):
    c = observation['camera']; d = np.asarray(xyz)-c['origin_m']
    depth = float(d@c['forward'])
    return np.array([d@c['right'], d@c['up']])/depth, depth


def receptor(observation, xyz):
    uv, _ = project(observation, xyz)
    return int(np.argmin(np.sum((np.asarray(observation['retinal_centers'])-uv)**2, axis=1)))


def eye_goal(task):
    return [*task['positions'][task['target']], .52 if task['goal']=='marker' else .16]


def score(task, rows, answer):
    target = np.asarray(task['positions'][task['target']])
    observations = [r['observation'] for r in rows]
    inside = [project(o, eye_goal(task))[1] > 0 and
              np.max(np.abs(project(o, eye_goal(task))[0])) <= o['eye_config']['center_half_width']
              for o in observations]
    stable = [b and np.linalg.norm(o['eye_velocity_rad_s']) < .08 for b,o in zip(inside,observations)]
    distances = [float(np.linalg.norm(np.array([o['pointer']['x'],o['pointer']['y']])-target)) for o in observations]
    held = 0; first_stable = None; longest = 0
    for i, ok in enumerate(stable):
        held = held+1 if ok else 0
        longest = max(longest, held)
        if held >= 6 and first_stable is None: first_stable = (i-5)*DT
    eye_ok = all(stable[-6:])
    arrived = [d <= .15 for d in distances]
    first_arrival = next((i*DT for i,v in enumerate(arrived) if v), None)
    # A command retained from the previous question is not a new decision.
    # Keep it in the trajectory, but score decisions actually emitted here.
    decisions = [(i*DT, r.get('own_decision')) for i,r in enumerate(rows)
                 if r.get('own_decision') is not None]
    move_at = next((t for t,d in decisions if d['move']), None)
    hand_ok = all(arrived[-6:])
    # Coordination is judged against genuine fixation, never used to run the hand.
    order_eligible = not arrived[0]
    order_ok = (first_stable is not None and move_at is not None and
                move_at >= first_stable+.25 and first_arrival is not None and first_arrival >= first_stable)
    # Already-at-target cases test goal maintenance; they are excluded from the
    # eye-before-hand denominator rather than credited as a new pointing action.
    order_result = bool(order_ok) if order_eligible else None
    word_ok = None if task['label'] is None else answer == task['label']
    if task['stage'] == 'gaze':
        success = eye_ok
    else:
        success = eye_ok and hand_ok and order_result is not False and word_ok is not False
    return {'id': task['id'], 'stage': task['stage'], 'split': task['split'], 'success': bool(success),
                'eye_success': bool(eye_ok), 'eye_initially_inside': bool(inside[0]),
                'eye_entered_from_outside': bool(not inside[0] and any(inside)),
                'eye_final_inside': bool(inside[-1]), 'eye_longest_stable_s': longest*DT,
                'first_fixation_s': first_stable, 'hand_success': bool(hand_ok), 'hand_initially_arrived': bool(arrived[0]),
                'hand_entered_from_outside': bool(not arrived[0] and any(arrived)),
                'hand_final_error_m': distances[-1], 'first_arrival_s': first_arrival, 'first_move_command_s': move_at,
                'eye_before_hand': order_result, 'coordination_eligible': order_eligible,
                'new_decisions': len(decisions), 'wait_decisions': sum(not d['move'] for _,d in decisions),
                'move_decisions': sum(d['move'] for _,d in decisions),
                'inherited_move': bool(rows[0].get('own_intent') and rows[0]['own_intent']['move']),
                'hand_initial_speed_m_s': float(np.hypot(observations[0]['pointer']['vx'],observations[0]['pointer']['vy'])),
                'hand_distance_during_first_2s_m': sum(float(np.hypot(b['pointer']['x']-a['pointer']['x'],
                    b['pointer']['y']-a['pointer']['y'])) for a,b in itertools.pairwise(observations[:40])),
                'answer': answer, 'expected': task['label'], 'word_correct': word_ok}


def trial(a, task, *, teaching=False, collect=False):
    """An entire current request, never restored or reinitialized per question."""
    s = a.session; w = s.world
    w.set_scene(task['items'], positions=task['positions'])
    xy = task['positions'][task['target']]
    utterance = task['statement'] if teaching else task['text']
    frames = list(s.sensor.frames(utterance))
    if len(frames) > QUESTION_TICKS: raise ValueError('utterance exceeds complete registered request window')
    rows = []; xs=[]; eye_y=[]; hand_y=[]; move_y=[]
    intent = a.executor.last_intent
    teaching_wait = [w.pointer.x, w.pointer.y]
    fixed = 0
    samples = []
    for i in range(TICKS):
        decision = None
        # Markers are explicit cues, not an inference metadata parameter.
        w.marker = xy if task['stage']=='gaze' or ((teaching or task['stage']=='coordination') and i < 20) else None
        if i >= QUESTION_TICKS and i % DECISION_TICKS == 0:
            before = time.perf_counter_ns()
            decision = a.motor.intent(window(a.motor.layout, rows))
            a.meter['motor_inference_ns'] = a.meter.get('motor_inference_ns',0)+time.perf_counter_ns()-before
            a.executor.accept(decision, rows[-1]['observation'], w)
            intent = a.executor.last_intent
        own_eye, own_hand = a.executor.commands(w)
        teacher_eye = teacher_hand = None
        if teaching:
            teacher_eye = w.eye_servo(teacher_eye_angle(w, xy, z=eye_goal(task)[2]))
            teacher_move = task['stage']!='gaze' and fixed>=6 and i>=QUESTION_TICKS
            hand_target = xy if teacher_move else teaching_wait
            teacher_hand = np.clip(3*(np.asarray(hand_target)-[w.pointer.x,w.pointer.y])
                                  -.9*np.array([w.pointer.vx,w.pointer.vy]), -1, 1)
        before = time.perf_counter_ns()
        row = s.tick(frames[i] if i<len(frames) else None,
                     eye=own_eye if teacher_eye is None else teacher_eye,
                     hand=own_hand if teacher_hand is None else teacher_hand)
        a.meter['sensor_core_body_ns'] = a.meter.get('sensor_core_body_ns',0)+time.perf_counter_ns()-before
        row.update(own_intent=intent, own_decision=decision,
                   own_eye_action=own_eye.tolist(), own_hand_action=own_hand.tolist(),
                   assistance=bool(teaching), teacher_eye_action=None if teacher_eye is None else teacher_eye.tolist(),
                   teacher_hand_action=None if teacher_hand is None else teacher_hand.tolist(),
                   utterance=utterance, executor=a.executor.state())
        rows.append(row)
        ob = row['observation']
        uv, depth = project(ob, eye_goal(task))
        stable = depth>0 and max(abs(uv))<=w.eye_config.center_half_width and np.linalg.norm(ob['eye_velocity_rad_s'])<.08
        fixed = fixed+1 if stable else 0
        if (collect or teaching) and i >= QUESTION_TICKS-1 and (i+1) % DECISION_TICKS == 0:
            # Labels are separate teacher/scorer data from the recorded acquisition geometry.
            move = task['stage']!='gaze' and fixed>=6
            xs.append(window(a.motor.layout, rows))
            eye_y.append(receptor(ob, eye_goal(task)))
            hand_y.append(receptor(ob, [*xy,.16]) if move else -1)
            move_y.append(int(move))
            samples.append({'time_us': row['activity']['time_us'], 'move': move,
                                'source': 'demonstration' if teaching else 'answer-free-request'})
    # A genuine, answer-free one-second naming question follows the fixed motor
    # window, whether or not the student looked/pointed correctly. It never waits
    # for a scoring gate and keeps both learned actuator outputs connected.
    word_rows = []
    motor_rows = list(rows)
    if task['label'] is not None and not teaching:
        word_frames = list(s.sensor.frames(task['word_question']))
        if len(word_frames)>20: raise ValueError('complete naming question exceeds one second')
        for i in range(20):
            decision = None
            if i % DECISION_TICKS == 0:
                before = time.perf_counter_ns()
                decision = a.motor.intent(window(a.motor.layout, rows))
                a.meter['motor_inference_ns'] = a.meter.get('motor_inference_ns',0)+time.perf_counter_ns()-before
                a.executor.accept(decision, rows[-1]['observation'], w)
                intent = a.executor.last_intent
            eye, hand = a.executor.commands(w)
            before = time.perf_counter_ns()
            row = s.tick(word_frames[i] if i<len(word_frames) else None, eye=eye, hand=hand)
            a.meter['sensor_core_body_ns'] = a.meter.get('sensor_core_body_ns',0)+time.perf_counter_ns()-before
            row.update(own_intent=intent, own_decision=decision,
                       own_eye_action=eye.tolist(), own_hand_action=hand.tolist(),
                       assistance=False, teacher_eye_action=None, teacher_hand_action=None,
                       utterance=task['word_question'], executor=a.executor.state())
            word_rows.append(row); rows.append(row)
    xword = window(a.words.layout, word_rows or rows)
    before = time.perf_counter_ns()
    answer = int(a.words.predict(xword[None])[0].argmax()) if task['label'] is not None and not teaching else None
    a.meter['word_inference_ns'] = a.meter.get('word_inference_ns',0)+time.perf_counter_ns()-before
    result = score(task, motor_rows, answer)
    if teaching:
        result['word_correct'] = None
        result['eye_before_hand'] = None
        result['coordination_eligible'] = False
        result['success'] = bool(result['eye_success'] and
                                 (task['stage']=='gaze' or result['hand_success']))
        result['assisted_goal_reached'] = result['success']
    result['autonomous_success'] = None if teaching else result['success']
    result['motor_window_s'] = TICKS*DT
    if word_rows:
        result['post_naming'] = score(task, rows, answer)
    result.update(teaching=teaching, identity=a.identity,
                  start_us=int(rows[0]['activity']['time_us'])-s.dt_us, end_us=s.engine.time_us)
    rows[-1]['expression'] = {'selected': answer, 'expected_for_scoring': task['label']}
    data = {'x': np.asarray(xs,dtype=np.float32), 'eye_y': np.asarray(eye_y,dtype=np.int64),
                'hand_y': np.asarray(hand_y,dtype=np.int64), 'move_y': np.asarray(move_y,dtype=np.int64),
                'word_x': xword[None] if collect and task['label'] is not None else np.empty((0,8,a.words.features),dtype=np.float32),
                'word_y': np.asarray([task['label']] if collect and task['label'] is not None else [],dtype=np.int64)}
    return rows, data, result, samples


def interval(a, seconds):
    """Keep the scene and learned commands during declared spaced review gaps."""
    rows=[]
    for i in range(round(seconds/DT)):
        if len(rows)>=QUESTION_TICKS and i%DECISION_TICKS==0:
            intent=a.motor.intent(window(a.motor.layout, rows[-120:]))
            a.executor.accept(intent,rows[-1]['observation'],a.session.world)
        eye,hand=a.executor.commands(a.session.world)
        rows.append(a.session.tick(eye=eye,hand=hand))
    return rows
