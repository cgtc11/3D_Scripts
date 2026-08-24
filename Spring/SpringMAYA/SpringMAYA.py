# -*- coding: utf-8 -*-
"""SpringMaya 003 / Maya 2025以降 / PySide6

単一ファイル版。Mayaのスクリプトエディタ(Python)から実行できます。
"""

import math
import sys
import traceback
from collections import OrderedDict

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui
from shiboken6 import wrapInstance

from PySide6 import QtCore, QtWidgets

BUILD = "003"
EPS = 1.0e-8


class Vec3(object):
    __slots__ = ("x", "y", "z")

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return cls(value.x, value.y, value.z)
        return cls(value.x, value.y, value.z)

    def copy(self):
        return Vec3(self.x, self.y, self.z)

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, value):
        return Vec3(self.x * value, self.y * value, self.z * value)

    def __rmul__(self, value):
        return self.__mul__(value)

    def __truediv__(self, value):
        if abs(value) < EPS:
            return Vec3()
        return Vec3(self.x / value, self.y / value, self.z / value)

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length_sq(self):
        return self.dot(self)

    def length(self):
        return math.sqrt(self.length_sq())

    def normalized(self):
        length = self.length()
        if length < EPS:
            return Vec3()
        return self / length

    def is_zero(self):
        return self.length_sq() < EPS * EPS

    def as_tuple(self):
        return (self.x, self.y, self.z)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))

def distance(a, b):
    return (b - a).length()

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


PROXY_SUFFIX = "_SpringNull_MAYA"
SPHERE_TAG = "SpringMagicSphere"
BOX_TAG = "SpringMagicBox"
WIND_TAG = "SpringMagicWind"
GRAVITY_TAG = "SpringMagicGravity"
TYPE_PROP = "SpringMagicType"

class CancelledError(RuntimeError):
    pass

class Spring(object):
    def __init__(self, ratio=0.3, twist_ratio=0.3, tension=0.5, extend=0.0, inertia=0.0):
        self.ratio = float(ratio)
        self.twist_ratio = float(twist_ratio)
        self.tension = float(tension)
        self.extend = float(extend)
        self.inertia = float(inertia)

class SpringMagicSettings(object):
    def __init__(
        self,
        start_frame,
        end_frame,
        sub_div=1,
        is_loop=False,
        is_pose_match=False,
        is_collision=False,
        collision_margin=0.0,
        collision_recovery_stiffness=0.8,  # デフォルト値を0.8に変更
        collision_chain_follow=0.65,
        include_root=False,
        include_branch_points=True,
        wipe_subframe=True,
        use_wind=False,
        use_gravity=False,
    ):
        self.start_frame = int(start_frame)
        self.end_frame = int(end_frame)
        self.sub_div = max(1, int(sub_div))
        self.is_loop = bool(is_loop)
        self.is_pose_match = bool(is_pose_match)
        self.is_collision = bool(is_collision)
        self.collision_margin = max(0.0, float(collision_margin))
        self.collision_recovery_stiffness = clamp(float(collision_recovery_stiffness), 0.01, 1.0)
        self.collision_chain_follow = clamp(float(collision_chain_follow), 0.0, 1.0)
        self.include_root = bool(include_root)
        self.include_branch_points = bool(include_branch_points)
        self.wipe_subframe = bool(wipe_subframe)
        self.use_wind = bool(use_wind)
        self.use_gravity = bool(use_gravity)
        self.wind = None
        self.gravity = None


def _node_handle(node):
    uuids = cmds.ls(node, uuid=True)
    return uuids[0] if uuids else node

def _valid_node(node):
    return cmds.objExists(node)

def _parent(node):
    p = cmds.listRelatives(node, parent=True, fullPath=True)
    return p[0] if p else None

def _children(node):
    c = cmds.listRelatives(node, children=True, fullPath=True, type='transform')
    return c if c else []

def _world_matrix(node):
    return cmds.xform(node, q=True, ws=True, m=True)

def _world_position(node):
    pos = cmds.xform(node, q=True, ws=True, t=True)
    return Vec3(pos[0], pos[1], pos[2])

def _world_axis(node, row_index):
    mat = _world_matrix(node)
    idx = row_index * 4
    return Vec3(mat[idx], mat[idx+1], mat[idx+2]).normalized()

def _matrix_scale(node):
    mat = _world_matrix(node)
    sx = Vec3(mat[0], mat[1], mat[2]).length()
    sy = Vec3(mat[4], mat[5], mat[6]).length()
    sz = Vec3(mat[8], mat[9], mat[10]).length()
    return Vec3(sx, sy, sz)

def _set_world_rotation_from_basis(node, x_axis, y_axis, z_axis, position=None):
    if position is None:
        position = _world_position(node)
    
    mat_list = [
        x_axis.x, x_axis.y, x_axis.z, 0.0,
        y_axis.x, y_axis.y, y_axis.z, 0.0,
        z_axis.x, z_axis.y, z_axis.z, 0.0,
        position.x, position.y, position.z, 1.0
    ]
    
    mmat = om.MMatrix(mat_list)
    mtr = om.MTransformationMatrix(mmat)
    rot = mtr.rotation(True)
    
    sel = om.MSelectionList()
    sel.add(node)
    dag = sel.getDagPath(0)
    transformFn = om.MFnTransform(dag)
    transformFn.setRotation(rot, om.MSpace.kWorld)

def _aim_x_axis(node, target, up_vector, reference_up=None, continuity_up=None):
    obj_pos = _world_position(node)
    x_axis = (target - obj_pos).normalized()
    if x_axis.is_zero():
        return False

    if reference_up is None:
        reference_up = _world_axis(node, 1)
    if continuity_up is None:
        continuity_up = _world_axis(node, 1)

    desired_up = up_vector.normalized()
    reference_up = reference_up.normalized()
    continuity_up = continuity_up.normalized()

    def projected(axis):
        if axis.is_zero():
            return Vec3()
        result = axis - x_axis * axis.dot(x_axis)
        return result.normalized() if not result.is_zero() else Vec3()

    desired_y = projected(desired_up)
    ref_y = projected(reference_up)
    continuity_y = projected(continuity_up)

    parallel_amount = abs(desired_up.dot(x_axis)) if not desired_up.is_zero() else 1.0
    if parallel_amount > 0.965 and not continuity_y.is_zero():
        y_axis = continuity_y
    elif not desired_y.is_zero():
        y_axis = desired_y
        if not continuity_y.is_zero() and y_axis.dot(continuity_y) < 0.0:
            y_axis = -y_axis
        if not continuity_y.is_zero():
            y_axis = (y_axis * 0.82 + continuity_y * 0.18).normalized()
    elif not continuity_y.is_zero():
        y_axis = continuity_y
    elif not ref_y.is_zero():
        y_axis = ref_y
    else:
        # 修正: MayaのY-Up環境に合わせてフォールバックをY軸基準に変更
        fallback = Vec3(0.0, 1.0, 0.0) if abs(x_axis.y) < 0.9 else Vec3(0.0, 0.0, 1.0)
        y_axis = projected(fallback)

    if y_axis.is_zero():
        return False

    if not ref_y.is_zero() and y_axis.dot(ref_y) < -0.25:
        y_axis = -y_axis

    z_axis = x_axis.cross(y_axis).normalized()
    if z_axis.is_zero():
        return False
    y_axis = z_axis.cross(x_axis).normalized()
    _set_world_rotation_from_basis(node, x_axis, y_axis, z_axis, obj_pos)
    return True

def _unique_scene_name(base):
    if not cmds.objExists(base):
        return base
    index = 1
    while True:
        name = "{0}_{1:03d}".format(base, index)
        if not cmds.objExists(name):
            return name
        index += 1

def _set_type(node, value):
    if not cmds.attributeQuery(TYPE_PROP, node=node, exists=True):
        cmds.addAttr(node, ln=TYPE_PROP, dt='string')
    cmds.setAttr(f"{node}.{TYPE_PROP}", value, type='string')

def _get_type(node):
    if cmds.attributeQuery(TYPE_PROP, node=node, exists=True):
        return cmds.getAttr(f"{node}.{TYPE_PROP}")
    return ""

def _scene_nodes_by_type(value):
    result = []
    transforms = cmds.ls(type='transform')
    for node in transforms:
        if _get_type(node) == value:
            result.append(node)
    return result

_ANGLE_REFERENCE = {}

def _basis_components_in_parent(node, axis):
    parent = _parent(node)
    axis = axis.normalized()
    if parent is None:
        return axis.copy(), None
    px = _world_axis(parent, 0)
    py = _world_axis(parent, 1)
    pz = _world_axis(parent, 2)
    local = Vec3(axis.dot(px), axis.dot(py), axis.dot(pz))
    return local, _node_handle(parent)

def _capture_angle_reference(node):
    x, parent_handle = _basis_components_in_parent(node, _world_axis(node, 0))
    y, _ = _basis_components_in_parent(node, _world_axis(node, 1))
    z, _ = _basis_components_in_parent(node, _world_axis(node, 2))
    return {
        "parent_handle": parent_handle,
        "x": x,
        "y": y,
        "z": z,
    }

def _reference_world_axis(node, reference, key):
    local = reference[key]
    parent = _parent(node)
    if parent is None or reference.get("parent_handle") is None:
        return local.normalized()
    px = _world_axis(parent, 0)
    py = _world_axis(parent, 1)
    pz = _world_axis(parent, 2)
    world = px * local.x + py * local.y + pz * local.z
    return world.normalized()

def _user_float(node, key, default):
    if cmds.attributeQuery(key, node=node, exists=True):
        return cmds.getAttr(f"{node}.{key}")
    return default

def _set_user_float(node, key, value):
    if not cmds.attributeQuery(key, node=node, exists=True):
        cmds.addAttr(node, ln=key, at='double')
    cmds.setAttr(f"{node}.{key}", float(value))

def _persist_angle_reference(node, reference):
    _set_user_float(node, "SM_AngleSaved", 1.0)
    _set_user_float(node, "SM_AngleHasParent", 1.0 if reference.get("parent_handle") is not None else 0.0)
    for key in ("x", "y", "z"):
        value = reference[key]
        _set_user_float(node, f"SM_Angle_{key.upper()}X", float(value.x))
        _set_user_float(node, f"SM_Angle_{key.upper()}Y", float(value.y))
        _set_user_float(node, f"SM_Angle_{key.upper()}Z", float(value.z))

def _load_persisted_angle_reference(node):
    if _user_float(node, "SM_AngleSaved", 0.0) == 0.0:
        return None
    has_parent = _user_float(node, "SM_AngleHasParent", 0.0) > 0.5
    axes = {}
    for key in ("x", "y", "z"):
        prefix = f"SM_Angle_{key.upper()}"
        axes[key] = Vec3(
            _user_float(node, prefix + "X", 0.0),
            _user_float(node, prefix + "Y", 0.0),
            _user_float(node, prefix + "Z", 0.0),
        )
    if axes["x"].is_zero() or axes["y"].is_zero():
        return None
    return {
        "parent_handle": 0 if has_parent else None,
        "x": axes["x"],
        "y": axes["y"],
        "z": axes["z"],
    }

def _saved_angle_reference(node):
    handle = _node_handle(node)
    reference = _ANGLE_REFERENCE.get(handle)
    if reference is not None:
        return reference
    reference = _load_persisted_angle_reference(node)
    if reference is not None:
        _ANGLE_REFERENCE[handle] = reference
    return reference

def save_reference_angles():
    count = 0
    for node in cmds.ls(sl=True) or []:
        reference = _capture_angle_reference(node)
        _ANGLE_REFERENCE[_node_handle(node)] = reference
        _persist_angle_reference(node, reference)
        count += 1
    return count

def clear_reference_angles():
    count = 0
    for node in cmds.ls(sl=True) or []:
        handle = _node_handle(node)
        had_reference = handle in _ANGLE_REFERENCE or _saved_angle_reference(node) is not None
        _ANGLE_REFERENCE.pop(handle, None)
        _set_user_float(node, "SM_AngleSaved", 0.0)
        if had_reference:
            count += 1
    return count

def _node_depth(node):
    depth = 0
    current = _parent(node)
    while current is not None:
        depth += 1
        current = _parent(current)
    return depth

def restore_reference_angles():
    nodes = [n for n in (cmds.ls(sl=True) or []) if _saved_angle_reference(n) is not None]
    nodes.sort(key=_node_depth)
    count = 0
    for node in nodes:
        reference = _saved_angle_reference(node)
        if reference is None:
            continue
        x = _reference_world_axis(node, reference, "x")
        y = _reference_world_axis(node, reference, "y")
        z = _reference_world_axis(node, reference, "z")
        _set_world_rotation_from_basis(node, x, y, z, _world_position(node))
        count += 1
    return count

def _select_nodes(nodes):
    valid_nodes = [n for n in nodes if cmds.objExists(n)]
    if valid_nodes:
        cmds.select(valid_nodes, replace=True)
    else:
        cmds.select(clear=True)

def _delete_rotation_keys(node, start_frame, end_frame):
    cmds.cutKey(node, time=(start_frame, end_frame), attribute=['rotateX', 'rotateY', 'rotateZ', 'rotate'])

def _delete_position_keys(node, start_frame, end_frame):
    cmds.cutKey(node, time=(start_frame, end_frame), attribute=['translateX', 'translateY', 'translateZ', 'translate'])

def _delete_non_integer_keys(node, start_frame, end_frame):
    attrs = cmds.listAnimatable(node)
    if not attrs:
        return
    for attr in attrs:
        keys = cmds.keyframe(attr, q=True, time=(start_frame, end_frame))
        if not keys:
            continue
        to_cut = [k for k in set(keys) if abs(k - round(k)) > 1e-5]
        for k in to_cut:
            cmds.cutKey(attr, time=(k, k))

def _smooth_euler_rotation_keys(node, start_frame, end_frame):
    try:
        cmds.filterCurve(f"{node}.rotate", f="euler")
        return True
    except Exception:
        return False

def _selected_chain_paths(nodes, include_root=False, include_branch_points=True):
    if not nodes:
        return []

    selected_by_handle = {_node_handle(node): node for node in nodes}
    selected_handles = set(selected_by_handle.keys())

    def selected_children(node):
        return [c for c in _children(node) if _node_handle(c) in selected_handles]

    def branch_reference_child(node, children):
        if not children:
            return None
        parent_pos = _world_position(node)
        x_axis = _world_axis(node, 0).normalized()
        if x_axis.is_zero():
            return children[0]

        best_child = children[0]
        best_score = -1.0e30
        for child in children:
            delta = _world_position(child) - parent_pos
            if delta.is_zero():
                score = -1.0e20
            else:
                score = delta.normalized().dot(x_axis)
            if score > best_score:
                best_score = score
                best_child = child
        return best_child

    roots = []
    for node in nodes:
        p = _parent(node)
        if p is None or _node_handle(p) not in selected_handles:
            roots.append(node)

    paths = []
    visited_starts = set()

    def walk_linear(start, is_selection_root=False):
        start_handle = _node_handle(start)
        if start_handle in visited_starts:
            return
        visited_starts.add(start_handle)

        path = [start]
        current = start

        while True:
            children = selected_children(current)
            if len(children) != 1:
                break
            current = children[0]
            path.append(current)

        branch_children = selected_children(current)
        stored_path = list(path)
        if len(branch_children) > 1 and include_branch_points:
            reference_child = branch_reference_child(current, branch_children)
            if reference_child is not None:
                stored_path.append(reference_child)

        if (
            not include_root
            and is_selection_root
            and _parent(start) is None
            and len(stored_path) > 1
        ):
            stored_path = stored_path[1:]

        if len(stored_path) >= 2:
            paths.append(stored_path)

        if len(branch_children) > 1:
            for child in branch_children:
                walk_linear(child, False)

    for root in roots:
        walk_linear(root, True)

    if not paths:
        raise ValueError(
            "計算できる親子チェーンがありません。選択した各枝で、計算する骨とその子を連続して選択してください。"
        )
    return paths

def _create_proxy(parent_node, child_node):
    name = _unique_scene_name(f"{parent_node}{PROXY_SUFFIX}")
    proxy = cmds.spaceLocator(name=name)[0]
    cmds.matchTransform(proxy, child_node, pos=True, rot=True)
    p = _parent(parent_node)
    if p:
        cmds.parent(proxy, p)
    cmds.hide(proxy)
    return proxy


class SpringData(object):
    def __init__(
        self, settings, spring, parent_node, child_node, grand_child, grand_parent,
        chain_index=0, chain_count=1,
    ):
        self.settings = settings
        self.spring = spring
        self.parent = parent_node
        self.child = child_node
        self.grand_child = grand_child
        self.grand_parent = grand_parent
        self.chain_index = max(0, int(chain_index))
        self.chain_count = max(1, int(chain_count))
        self.proxy = _create_proxy(parent_node, child_node)

        self.child_position = _world_position(child_node)
        self.grand_child_position = _world_position(grand_child) if grand_child is not None else None
        self.previous_child_position = self.child_position.copy()
        self.up_vector = _world_axis(parent_node, 1)
        self.stable_x_axis = _world_axis(parent_node, 0)
        self.stable_up_axis = _world_axis(parent_node, 1)
        self.bone_length = distance(_world_position(parent_node), self.child_position)
        self.start_parent_transform = _world_matrix(parent_node)
        self.start_child_transform = _world_matrix(child_node)
        
        saved_reference = _saved_angle_reference(parent_node)
        self.reference_is_saved = saved_reference is not None
        self.angle_reference = saved_reference if saved_reference is not None else _capture_angle_reference(parent_node)
        self.has_child_collide = False
        self.collision_active = False
        self.contact_active = False
        self.collision_recovery_active = False
        self.collision_recovery_position = self.child_position.copy()
        self.collision_recovery_parent_position = _world_position(parent_node)

    def sample_proxy(self, frame):
        cmds.matchTransform(self.proxy, self.child, pos=True, rot=True)

    def reference_axis(self, key):
        return _reference_world_axis(self.parent, self.angle_reference, key)

    def natural_target(self):
        parent_pos = _world_position(self.parent)
        reference_x = self.reference_axis("x")
        if reference_x.is_zero():
            reference_x = self.stable_x_axis
        return parent_pos + reference_x.normalized() * self.bone_length

    def update(self, has_collision, corrected_child_position):
        self.child_position = _world_position(self.child)
        if self.grand_child is not None and _valid_node(self.grand_child):
            self.grand_child_position = _world_position(self.grand_child)
        self.previous_child_position = corrected_child_position.copy()
        self.up_vector = _world_axis(self.parent, 1)
        self.stable_x_axis = _world_axis(self.parent, 0)
        self.stable_up_axis = _world_axis(self.parent, 1)
        self.has_child_collide = has_collision
        self.collision_active = bool(has_collision)

    def sync_final_pose(self):
        self.child_position = _world_position(self.child)
        if self.grand_child is not None and _valid_node(self.grand_child):
            self.grand_child_position = _world_position(self.grand_child)
        self.previous_child_position = self.child_position.copy()
        self.up_vector = _world_axis(self.parent, 1)
        self.stable_x_axis = _world_axis(self.parent, 0)
        self.stable_up_axis = _world_axis(self.parent, 1)

    def _collision_recovery_alpha(self):
        frame_alpha = self.settings.collision_recovery_stiffness
        return 1.0 - math.pow(1.0 - frame_alpha, 1.0 / float(self.settings.sub_div))

    def begin_collision_recovery(self, parent_pos, corrected_child_position):
        self.collision_recovery_active = True
        self.collision_recovery_position = corrected_child_position.copy()
        self.collision_recovery_parent_position = parent_pos.copy()

    def recovery_target(self, parent_pos, natural_child_position):
        if not self.collision_recovery_active:
            return natural_child_position.copy(), False

        parent_delta = parent_pos - self.collision_recovery_parent_position
        previous = self.collision_recovery_position + parent_delta
        alpha = self._collision_recovery_alpha()
        candidate = previous * (1.0 - alpha) + natural_child_position * alpha
        natural_length = distance(parent_pos, natural_child_position)
        if natural_length < EPS:
            natural_length = self.bone_length
        candidate = _keep_bone_length(
            parent_pos, candidate, natural_length, natural_child_position - parent_pos
        )

        self.collision_recovery_position = candidate.copy()
        self.collision_recovery_parent_position = parent_pos.copy()

        tolerance = max(1.0e-4, natural_length * 1.0e-4)
        if distance(candidate, natural_child_position) <= tolerance:
            self.collision_recovery_active = False
            self.collision_recovery_position = natural_child_position.copy()
            return natural_child_position.copy(), False
        return candidate, True

    def apply_inertia(self, current_child_position):
        ratio = self.spring.ratio / float(self.settings.sub_div)
        inertia_offset = Vec3()
        if self.spring.inertia > 0.0:
            ref_offset = current_child_position - self.child_position
            ref_length = ref_offset.length()
            if ref_length > EPS:
                offset_distance = (ref_offset * (1.0 - ratio) * (1.0 - self.spring.inertia)).length()
                inertia_offset = ref_offset.normalized() * (offset_distance / float(self.settings.sub_div))

        force_direction = self.child_position - self.previous_child_position
        force_distance = force_direction.length() * self.spring.inertia
        if force_direction.length() > EPS:
            inertia_offset = inertia_offset + force_direction.normalized() * (
                force_distance / float(self.settings.sub_div)
            )
        return inertia_offset

    def apply_wind(self, frame, natural_child_position):
        wind = self.settings.wind
        if wind is None or not _valid_node(wind):
            return Vec3()

        max_force = float(_user_float(wind, "MaxForce", 100.0))
        min_force = float(_user_float(wind, "MinForce", 0.5))
        frequency = max(0.0, float(_user_float(wind, "Frequency", 1.0)))
        tip_multiplier = clamp(float(_user_float(wind, "TipMultiplier", 2.5)), 1.0, 10.0)
        
        wind_direction = _world_axis(wind, 1).normalized()
        if wind_direction.is_zero():
            return Vec3()

        phase = (float(frame) * frequency * (2.0 * math.pi / 30.0)) - (self.chain_index * 0.55)
        wave = 0.5 * (math.sin(phase) + 1.0)
        force = min_force + (max_force - min_force) * wave
        if abs(force) < EPS:
            return Vec3()

        parent_pos = _world_position(self.parent)
        bone_axis = (natural_child_position - parent_pos).normalized()
        if bone_axis.is_zero():
            bone_axis = self.reference_axis("x")
        if bone_axis.is_zero():
            return Vec3()

        target_direction = wind_direction if force >= 0.0 else -wind_direction
        depth = float(self.chain_index + 1) / float(self.chain_count)
        depth_gain = 1.0 + (tip_multiplier - 1.0) * math.pow(depth, 1.35)

        bend = 1.0 - math.exp(-abs(force) * 0.004 * depth_gain)
        bend = clamp(bend, 0.0, 0.94)

        desired_axis = (bone_axis * (1.0 - bend) + target_direction * bend).normalized()
        if desired_axis.is_zero():
            return Vec3()

        desired_child = parent_pos + desired_axis * max(self.bone_length, EPS)
        return desired_child - natural_child_position

    def apply_gravity(self):
        gravity = self.settings.gravity
        if gravity is None or not _valid_node(gravity):
            return Vec3()
        strength = float(_user_float(gravity, "Strength", 1.0))
        
        direction = _world_axis(gravity, 1)
        return direction * (strength / float(self.settings.sub_div))

    def compute_up_vector(self):
        twist_ratio = self.spring.twist_ratio / float(self.settings.sub_div)
        cur_up = _world_axis(self.proxy, 1)
        prev_up = self.up_vector.normalized()
        reference_up = self.reference_axis("y")

        up = prev_up * (1.0 - twist_ratio) + cur_up * twist_ratio
        if up.is_zero():
            up = cur_up if not cur_up.is_zero() else reference_up
        if up.is_zero():
            up = Vec3(0.0, 1.0, 0.0)

        frame_anchor = 0.22
        anchor = 1.0 - math.pow(1.0 - frame_anchor, 1.0 / float(self.settings.sub_div))
        if not reference_up.is_zero():
            if up.dot(reference_up) < 0.0:
                up = -up
            up = (up.normalized() * (1.0 - anchor) + reference_up * anchor).normalized()
        return up.normalized()

    def aim_by_ratio(self, up_vector, new_child_position, corrected_child_position):
        ratio = self.spring.ratio / float(self.settings.sub_div)
        tension = self.spring.tension / (1.0 / (sigmoid(1.0 - float(self.settings.sub_div)) + 0.5))
        target = corrected_child_position * (1.0 - ratio) + new_child_position * ratio
        if self.has_child_collide and self.grand_child_position is not None and tension > 0.0:
            weight = (1.0 - ratio) * tension
            target = (target + self.grand_child_position * weight) / (1.0 + weight)
        _aim_x_axis(
            self.parent,
            target,
            up_vector,
            self.reference_axis("y"),
            self.stable_up_axis,
        )

    def extend_bone(self, corrected_child_position):
        if abs(self.spring.extend) < EPS:
            return
        parent_pos = _world_position(self.parent)
        desired = distance(parent_pos, corrected_child_position)
        length = self.bone_length * (1.0 - self.spring.extend) + desired * self.spring.extend
        x_axis = _world_axis(self.parent, 0)
        new_pos = parent_pos + x_axis * length
        cmds.xform(self.child, ws=True, t=(new_pos.x, new_pos.y, new_pos.z))


def _sphere_data(node):
    center = _world_position(node)
    scale = _matrix_scale(node)
    radius = 1.0 * max(scale.x, scale.y, scale.z)
    return center, max(EPS, radius)

def _box_data(node):
    center = _world_position(node)
    x_axis = _world_axis(node, 0)
    y_axis = _world_axis(node, 1)
    z_axis = _world_axis(node, 2)
    scale = _matrix_scale(node)
    return center, (x_axis, y_axis, z_axis), Vec3(scale.x, scale.y, scale.z)

def _keep_bone_length(parent_pos, candidate, bone_length, fallback_direction):
    direction = candidate - parent_pos
    if direction.is_zero():
        direction = fallback_direction
    if direction.is_zero():
        direction = Vec3(1.0, 0.0, 0.0)
    return parent_pos + direction.normalized() * bone_length


def _tangent_direction(normal, bone_direction):
    bone = bone_direction.normalized()
    n = normal.normalized()
    tangent = n - bone * n.dot(bone)
    if not tangent.is_zero():
        return tangent.normalized()
    
    # 修正: Y-Up環境に合わせてフォールバックをY軸基準に変更
    reference = Vec3(0.0, 1.0, 0.0)
    if abs(bone.dot(reference)) > 0.9:
        reference = Vec3(0.0, 0.0, 1.0)
        
    tangent = bone.cross(reference)
    if tangent.is_zero():
        tangent = Vec3(1.0, 0.0, 0.0)
    return tangent.normalized()

def _point_inside_sphere(point, center, radius):
    return distance(point, center) < radius

def _push_point_out_sphere(point, center, radius, fallback):
    direction = point - center
    if direction.is_zero():
        direction = fallback
    if direction.is_zero():
        direction = Vec3(1.0, 0.0, 0.0)
    return center + direction.normalized() * radius

def _closest_point_on_segment(point, start, end):
    axis = end - start
    denom = axis.length_sq()
    if denom < EPS:
        return start.copy(), 0.0
    t = clamp((point - start).dot(axis) / denom, 0.0, 1.0)
    return start + axis * t, t

def _obb_local(point, center, axes):
    delta = point - center
    return Vec3(delta.dot(axes[0]), delta.dot(axes[1]), delta.dot(axes[2]))

def _obb_world(local_point, center, axes):
    return center + axes[0] * local_point.x + axes[1] * local_point.y + axes[2] * local_point.z

def _point_inside_box(point, center, axes, half):
    p = _obb_local(point, center, axes)
    return abs(p.x) < half.x and abs(p.y) < half.y and abs(p.z) < half.z

def _box_escape_direction(point, center, axes, half, bone_direction):
    p = _obb_local(point, center, axes)
    candidates = [
        (half.x - p.x, axes[0]),
        (half.x + p.x, -axes[0]),
        (half.y - p.y, axes[1]),
        (half.y + p.y, -axes[1]),
        (half.z - p.z, axes[2]),
        (half.z + p.z, -axes[2]),
    ]
    bone = bone_direction.normalized()
    best = None
    for face_distance, normal in candidates:
        tangent = normal - bone * normal.dot(bone)
        tangent_len = tangent.length()
        score = max(0.0, face_distance) / max(0.02, tangent_len)
        if best is None or score < best[0]:
            best = (score, max(0.0, face_distance), normal, tangent)
    _, penetration, normal, tangent = best
    if tangent.is_zero():
        tangent = _tangent_direction(normal, bone)
    else:
        tangent = tangent.normalized()
    return tangent, penetration

def _segment_box_interval(start, end, center, axes, half):
    a = _obb_local(start, center, axes)
    b = _obb_local(end, center, axes)
    d = b - a
    t_min = 0.0
    t_max = 1.0
    for origin, direction, extent in (
        (a.x, d.x, half.x),
        (a.y, d.y, half.y),
        (a.z, d.z, half.z),
    ):
        if abs(direction) < EPS:
            if origin < -extent or origin > extent:
                return False, None, None
            continue
        inv = 1.0 / direction
        t1 = (-extent - origin) * inv
        t2 = (extent - origin) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return False, None, None
    return True, t_min, t_max

def _resolve_against_sphere(parent_pos, child_pos, center, radius, bone_length, fallback, skin):
    result = child_pos
    changed = False
    bone_dir = (result - parent_pos).normalized()
    target = radius + skin

    child_delta = result - center
    child_dist = child_delta.length()
    if child_dist < target:
        normal = child_delta.normalized()
        if normal.is_zero():
            normal = (parent_pos - center).normalized()
        tangent = _tangent_direction(normal, bone_dir)
        penetration = target - child_dist
        pushed = result + tangent * max(penetration, skin)
        result = _keep_bone_length(parent_pos, pushed, bone_length, fallback)
        changed = True
        bone_dir = (result - parent_pos).normalized()

    if _point_inside_sphere(parent_pos, center, target):
        return changed, result

    closest, bone_t = _closest_point_on_segment(center, parent_pos, result)
    delta = closest - center
    dist = delta.length()
    if dist < target:
        normal = delta.normalized()
        if normal.is_zero():
            normal = (parent_pos - center).normalized()
        tangent = _tangent_direction(normal, bone_dir)
        penetration = target - dist
        lever = max(0.12, bone_t)
        pushed = result + tangent * (max(penetration, skin) / lever)
        result = _keep_bone_length(parent_pos, pushed, bone_length, fallback)
        changed = True
    return changed, result

def _resolve_against_box(parent_pos, child_pos, center, axes, half, bone_length, fallback, skin):
    result = child_pos
    changed = False
    inflated = Vec3(half.x + skin, half.y + skin, half.z + skin)
    bone_dir = (result - parent_pos).normalized()

    if _point_inside_box(result, center, axes, inflated):
        tangent, penetration = _box_escape_direction(result, center, axes, inflated, bone_dir)
        pushed = result + tangent * max(penetration + skin, skin)
        result = _keep_bone_length(parent_pos, pushed, bone_length, fallback)
        changed = True
        bone_dir = (result - parent_pos).normalized()

    if _point_inside_box(parent_pos, center, axes, inflated):
        return changed, result

    hit, enter_t, exit_t = _segment_box_interval(parent_pos, result, center, axes, inflated)
    if hit and enter_t is not None and exit_t is not None:
        t = clamp((enter_t + exit_t) * 0.5, 0.0, 1.0)
        inside_point = parent_pos + (result - parent_pos) * t
        tangent, penetration = _box_escape_direction(
            inside_point, center, axes, inflated, bone_dir
        )
        lever = max(0.12, t)
        pushed = result + tangent * (max(penetration + skin, skin) / lever)
        result = _keep_bone_length(parent_pos, pushed, bone_length, fallback)
        changed = True
    return changed, result

def _strict_resolve_child_position(parent_pos, child_pos, spheres, boxes, margin, max_iterations=40):
    if not spheres and not boxes:
        return False, child_pos
    bone_length = distance(parent_pos, child_pos)
    if bone_length < EPS:
        return False, child_pos

    result = child_pos.copy()
    fallback = (child_pos - parent_pos).normalized()
    margin = max(0.0, float(margin))
    skin = max(1.0e-3, margin * 0.05)
    collided = False

    for _ in range(max_iterations):
        changed = False
        for node in spheres:
            center, base_radius = _sphere_data(node)
            hit, result2 = _resolve_against_sphere(
                parent_pos, result, center, base_radius + margin, bone_length, fallback, skin
            )
            if hit:
                result = result2
                changed = True
                collided = True
        for node in boxes:
            center, axes, half = _box_data(node)
            half = Vec3(half.x + margin, half.y + margin, half.z + margin)
            hit, result2 = _resolve_against_box(
                parent_pos, result, center, axes, half, bone_length, fallback, skin
            )
            if hit:
                result = result2
                changed = True
                collided = True
        if not changed:
            break
    return collided, result

def _strict_resolve_pose(data, spheres, boxes, up_vector):
    if not data.settings.is_collision or (not spheres and not boxes):
        return False
    collided = False
    for _ in range(10):
        parent_pos = _world_position(data.parent)
        child_pos = _world_position(data.child)
        hit, target = _strict_resolve_child_position(
            parent_pos,
            child_pos,
            spheres,
            boxes,
            data.settings.collision_margin,
        )
        if not hit:
            break
        collided = True
        if not _aim_x_axis(
            data.parent,
            target,
            up_vector,
            data.reference_axis("y"),
            data.stable_up_axis,
        ):
            break
    return collided

def _collision_chain_follow_alpha(settings, iterations):
    strength = clamp(settings.collision_chain_follow, 0.0, 1.0)
    if strength <= EPS:
        return 0.0
    steps = max(1.0, float(settings.sub_div) * float(max(1, iterations)))
    return 1.0 - math.pow(1.0 - strength, 1.0 / steps)

def _bend_follow_weight(upper_direction, lower_direction):
    upper = upper_direction.normalized()
    lower = lower_direction.normalized()
    if upper.is_zero() or lower.is_zero():
        return 0.0
    dot = clamp(upper.dot(lower), -1.0, 1.0)
    straight_dot = math.cos(math.radians(25.0))
    if dot >= straight_dot:
        return 0.0
    return clamp((straight_dot - dot) / straight_dot, 0.0, 1.0)

def _apply_collision_chain_follow(chain_data_paths, spheres, boxes):
    if not chain_data_paths:
        return False
    if not spheres and not boxes:
        return False

    iterations = 3
    alpha = _collision_chain_follow_alpha(chain_data_paths[0][0].settings, iterations) if chain_data_paths[0] else 0.0
    if alpha <= EPS:
        return False

    changed_any = False
    for _ in range(iterations):
        for chain in chain_data_paths:
            if len(chain) < 2:
                continue
            pull_flags = [bool(data.contact_active) for data in chain]
            for index in range(len(chain) - 2, -1, -1):
                if not pull_flags[index + 1]:
                    continue

                upper_data = chain[index]
                lower_data = chain[index + 1]
                parent_pos = _world_position(upper_data.parent)
                joint_pos = _world_position(upper_data.child)
                lower_tip = _world_position(lower_data.child)
                upper_dir = joint_pos - parent_pos
                lower_dir = lower_tip - joint_pos
                bend_weight = _bend_follow_weight(upper_dir, lower_dir)
                if bend_weight <= EPS:
                    continue

                descendant_dir = (lower_tip - parent_pos).normalized()
                current_dir = upper_dir.normalized()
                if descendant_dir.is_zero() or current_dir.is_zero():
                    continue

                amount = alpha * bend_weight
                desired_dir = (current_dir * (1.0 - amount) + descendant_dir * amount).normalized()
                if desired_dir.is_zero():
                    continue

                up_vector = upper_data.compute_up_vector()
                target = parent_pos + desired_dir * upper_data.bone_length
                if _aim_x_axis(
                    upper_data.parent,
                    target,
                    up_vector,
                    upper_data.reference_axis("y"),
                    upper_data.stable_up_axis,
                ):
                    changed_any = True
                    pull_flags[index] = True

        for chain in chain_data_paths:
            for data in chain:
                up_vector = data.compute_up_vector()
                if _strict_resolve_pose(data, spheres, boxes, up_vector):
                    data.collision_active = True
                    data.contact_active = True
                    corrected = _world_position(data.child)
                    data.begin_collision_recovery(_world_position(data.parent), corrected)
                    changed_any = True

    return changed_any

def _detect_collision(data, parent_pos, desired_child_pos, spheres, boxes):
    if not data.settings.is_collision or (not spheres and not boxes):
        data.collision_recovery_active = False
        return False, False, desired_child_pos, data.child_position.copy()

    natural_target = desired_child_pos.copy()
    candidate, recovering = data.recovery_target(parent_pos, natural_target)

    hit, target = _strict_resolve_child_position(
        parent_pos,
        candidate,
        spheres,
        boxes,
        data.settings.collision_margin,
        max_iterations=24,
    )

    if hit:
        data.begin_collision_recovery(parent_pos, target)
        corrected = target.copy()
        return True, True, target, corrected

    if recovering:
        corrected = candidate.copy()
        return False, True, candidate, corrected

    return False, False, natural_target, data.child_position.copy()

def _progress(callback, value, message=None):
    if callback is None:
        return
    keep_going = callback(clamp(float(value), 0.0, 100.0), message)
    if keep_going is False:
        raise CancelledError("処理がキャンセルされました。")

def start_compute(spring, settings, progression_callback=None):
    selected = cmds.ls(sl=True) or []
    if not selected:
        raise ValueError("スプリング計算する親子ノードを選択してください。")
    if settings.end_frame <= settings.start_frame:
        raise ValueError("終了フレームは開始フレームより後にしてください。")

    paths = _selected_chain_paths(selected, settings.include_root, settings.include_branch_points)
    selected_original = list(selected)
    spring_data = OrderedDict()
    chain_data_paths = []
    proxies = []

    wind_nodes = _scene_nodes_by_type(WIND_TAG) if settings.use_wind else []
    settings.wind = wind_nodes[0] if wind_nodes else None
    gravity_nodes = _scene_nodes_by_type(GRAVITY_TAG) if settings.use_gravity else []
    settings.gravity = gravity_nodes[0] if gravity_nodes else None
    spheres = _scene_nodes_by_type(SPHERE_TAG) if settings.is_collision else []
    boxes = _scene_nodes_by_type(BOX_TAG) if settings.is_collision else []

    try:
        cmds.currentTime(settings.start_frame, update=True)
        for path in paths:
            chain_data = []
            segment_count = max(1, len(path) - 1)
            for index, parent_node in enumerate(path[:-1]):
                child = path[index + 1]
                grand_child = path[index + 2] if index + 2 < len(path) else None
                grand_parent = _parent(parent_node)
                data = SpringData(
                    settings, spring, parent_node, child, grand_child, grand_parent,
                    chain_index=index, chain_count=segment_count,
                )
                spring_data[_node_handle(parent_node)] = data
                chain_data.append(data)
                proxies.append(data.proxy)
            if chain_data:
                chain_data_paths.append(chain_data)

        if settings.is_pose_match:
            sample_count = settings.end_frame - settings.start_frame + 1
            for offset, frame in enumerate(range(settings.start_frame, settings.end_frame + 1)):
                cmds.currentTime(frame, update=True)
                for data in spring_data.values():
                    data.sample_proxy(frame)
                _progress(progression_callback, (offset + 1) * 15.0 / float(max(1, sample_count)), "ポーズ合わせをサンプル中")

        for data in spring_data.values():
            _delete_rotation_keys(data.parent, settings.start_frame, settings.end_frame)
            if abs(spring.extend) > EPS:
                _delete_position_keys(data.child, settings.start_frame, settings.end_frame)

        cmds.currentTime(settings.start_frame, update=True)
        for data in spring_data.values():
            cmds.xform(data.parent, ws=True, m=data.start_parent_transform)
            if abs(spring.extend) > EPS:
                cmds.xform(data.child, ws=True, m=data.start_child_transform)
                
            cmds.setKeyframe(data.parent, attribute='rotate', t=settings.start_frame)
            if abs(spring.extend) > EPS:
                cmds.setKeyframe(data.child, attribute='translate', t=settings.start_frame)

        step = 1.0 / float(settings.sub_div)
        frames = []
        frame = settings.start_frame + step
        while frame <= settings.end_frame + 1e-6:
            frames.append(frame)
            frame += step
        if settings.is_loop:
            frame = float(settings.start_frame)
            while frame <= settings.end_frame + 1e-6:
                frames.append(frame)
                frame += step

        start_progress = 15.0 if settings.is_pose_match else 0.0
        total = max(1, len(frames))
        
        for frame_index, frame in enumerate(frames):
            cmds.currentTime(frame, update=True)
            for data in spring_data.values():
                grand_parent_data = None
                if data.grand_parent is not None:
                    grand_parent_data = spring_data.get(_node_handle(data.grand_parent))

                parent_pos = _world_position(data.parent)
                new_child_pos = data.natural_target()
                new_child_pos = new_child_pos + data.apply_inertia(new_child_pos)
                new_child_pos = new_child_pos + data.apply_wind(frame, new_child_pos)
                new_child_pos = new_child_pos + data.apply_gravity()

                has_collision, collision_active, new_child_pos, corrected = _detect_collision(
                    data, parent_pos, new_child_pos, spheres, boxes
                )

                up_vector = data.compute_up_vector()
                data.aim_by_ratio(up_vector, new_child_pos, corrected)
                
                if _strict_resolve_pose(data, spheres, boxes, up_vector):
                    has_collision = True
                    collision_active = True
                    corrected = _world_position(data.child)
                    data.begin_collision_recovery(_world_position(data.parent), corrected)
                
                data.extend_bone(corrected)
                data.contact_active = bool(has_collision)
                data.update(collision_active, corrected)
                if grand_parent_data is not None:
                    grand_parent_data.has_child_collide = collision_active

            if settings.is_collision and settings.collision_chain_follow > EPS:
                if _apply_collision_chain_follow(chain_data_paths, spheres, boxes):
                    for data in spring_data.values():
                        data.sync_final_pose()

            for data in spring_data.values():
                cmds.setKeyframe(data.parent, attribute='rotate', t=frame)
                if abs(spring.extend) > EPS:
                    cmds.setKeyframe(data.child, attribute='translate', t=frame)

            progress = start_progress + (frame_index + 1) * (100.0 - start_progress) / float(total)
            _progress(progression_callback, progress, "スプリング計算中")
            if frame_index % 5 == 0:
                cmds.refresh()

        if settings.wipe_subframe and settings.sub_div > 1:
            for data in spring_data.values():
                _delete_non_integer_keys(data.parent, settings.start_frame, settings.end_frame)
                if abs(spring.extend) > EPS:
                    _delete_non_integer_keys(data.child, settings.start_frame, settings.end_frame)

        for data in spring_data.values():
            _smooth_euler_rotation_keys(data.parent, settings.start_frame, settings.end_frame)

        _progress(progression_callback, 100.0, "完了")
    finally:
        for proxy in proxies:
            if _valid_node(proxy):
                cmds.delete(proxy)
        try:
            _select_nodes(selected_original)
            cmds.refresh()
        except Exception:
            pass


def create_collision_sphere():
    selected = cmds.ls(sl=True) or []
    targets = selected if selected else [None]
    created = []
    for node in targets:
        radius = 10.0
        if node is not None:
            children = _children(node)
            if children:
                radius = max(1.0, distance(_world_position(node), _world_position(children[0])) * 0.75)
        
        sph = cmds.polySphere(r=1.0, sx=16, sy=16)[0]
        cmds.scale(radius, radius, radius, sph)
        
        base_name = "SpringCollisionSphere" if node is None else f"{node}_collision_sphere"
        sph = cmds.rename(sph, _unique_scene_name(base_name))
        
        if node is not None:
            cmds.matchTransform(sph, node, pos=True)
            
        _set_type(sph, SPHERE_TAG)
        created.append(sph)
        
    if created:
        _select_nodes(created)
    cmds.refresh()
    return created

def create_collision_box():
    # 修正: MayaのpolyCubeは中心にピボットがあるため、オフセット計算を削除し純粋にマッチさせる
    selected = cmds.ls(sl=True) or []
    targets = selected if selected else [None]
    created = []
    for node in targets:
        size = 20.0
        if node is not None:
            children = _children(node)
            if children:
                size = max(2.0, distance(_world_position(node), _world_position(children[0])) * 1.5)
                
        box = cmds.polyCube(w=2.0, h=2.0, d=2.0)[0]
        half_size = size * 0.5
        cmds.scale(half_size, half_size, half_size, box)
        
        base_name = "SpringCollisionBox" if node is None else f"{node}_collision_box"
        box = cmds.rename(box, _unique_scene_name(base_name))
        
        if node is not None:
            cmds.matchTransform(box, node, pos=True, rot=True)
            
        _set_type(box, BOX_TAG)
        created.append(box)
        
    if created:
        _select_nodes(created)
    cmds.refresh()
    return created

def remove_collision_helpers():
    nodes = []
    for tag in (SPHERE_TAG, BOX_TAG, WIND_TAG, GRAVITY_TAG):
        nodes.extend(_scene_nodes_by_type(tag))
    unique = list(set(nodes))
    for node in unique:
        if _valid_node(node):
            cmds.delete(node)
    cmds.refresh()
    return len(unique)

def create_wind():
    wind = cmds.polyCone(r=5.0, h=15.0)[0]
    wind = cmds.rename(wind, _unique_scene_name("spring_wind"))
    _set_type(wind, WIND_TAG)
    _set_user_float(wind, "MaxForce", 100.0)
    _set_user_float(wind, "MinForce", 0.5)
    _set_user_float(wind, "Frequency", 1.0)
    _set_user_float(wind, "TipMultiplier", 2.5)
    cmds.select(wind)
    cmds.refresh()
    return wind

def _write_wind_values(wind_nodes, max_force, min_force, frequency, tip_multiplier):
    for wind in wind_nodes:
        _set_user_float(wind, "MaxForce", float(max_force))
        _set_user_float(wind, "MinForce", float(min_force))
        _set_user_float(wind, "Frequency", float(frequency))
        _set_user_float(wind, "TipMultiplier", float(tip_multiplier))
    return wind_nodes

def set_wind_values(max_force, min_force, frequency, tip_multiplier=2.5):
    wind_nodes = [n for n in (cmds.ls(sl=True) or []) if _get_type(n) == WIND_TAG]
    if not wind_nodes:
        wind_nodes = _scene_nodes_by_type(WIND_TAG)
    if not wind_nodes:
        wind_nodes = [create_wind()]
    return _write_wind_values(wind_nodes, max_force, min_force, frequency, tip_multiplier)

def sync_existing_wind_values(max_force, min_force, frequency, tip_multiplier=2.5):
    wind_nodes = _scene_nodes_by_type(WIND_TAG)
    if not wind_nodes:
        raise ValueError("風が有効ですが、風オブジェクトがありません。先に［風オブジェクト作成 / 値更新］を押してください。")
    return _write_wind_values(wind_nodes, max_force, min_force, frequency, tip_multiplier)


def create_gravity():
    gravity = cmds.polyCone(r=5.0, h=15.0)[0]
    gravity = cmds.rename(gravity, _unique_scene_name("spring_gravity"))
    _set_type(gravity, GRAVITY_TAG)
    _set_user_float(gravity, "Strength", 1.0)
    cmds.select(gravity)
    cmds.refresh()
    return gravity

def set_gravity_value(strength):
    gravity_nodes = [n for n in (cmds.ls(sl=True) or []) if _get_type(n) == GRAVITY_TAG]
    if not gravity_nodes:
        gravity_nodes = _scene_nodes_by_type(GRAVITY_TAG)
    if not gravity_nodes:
        gravity_nodes = [create_gravity()]
    for gravity in gravity_nodes:
        _set_user_float(gravity, "Strength", float(strength))
    return gravity_nodes

def sync_existing_gravity_value(strength):
    gravity_nodes = _scene_nodes_by_type(GRAVITY_TAG)
    if not gravity_nodes:
        raise ValueError("重力が有効ですが、重力オブジェクトがありません。先に［重力オブジェクト作成 / 値更新］を押してください。")
    for gravity in gravity_nodes:
        _set_user_float(gravity, "Strength", float(strength))
    return gravity_nodes


_POSE_COPY = {}

def copy_pose():
    global _POSE_COPY
    _POSE_COPY = {}
    for node in cmds.ls(sl=True) or []:
        _POSE_COPY[_node_handle(node)] = _world_matrix(node)
    return len(_POSE_COPY)

def paste_pose():
    count = 0
    for node in cmds.ls(sl=True) or []:
        tm = _POSE_COPY.get(_node_handle(node))
        if tm is not None:
            cmds.xform(node, ws=True, m=tm)
            count += 1
    cmds.refresh()
    return count

def straighten_selected():
    count = 0
    for node in cmds.ls(sl=True) or []:
        children = _children(node)
        if not children:
            continue
        target = _world_position(children[0])
        up = _world_axis(node, 1)
        if _aim_x_axis(node, target, up):
            count += 1
    cmds.refresh()
    return count


core = sys.modules[__name__]
_WINDOW = None

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr:
        return wrapInstance(int(ptr), QtWidgets.QWidget)
    return None

class SpringMayaDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SpringMayaDialog, self).__init__(parent or _maya_main_window())
        self.setObjectName("SpringMayaDialog")
        self.setWindowTitle(f"SpringMaya {BUILD}")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.Tool)
        self.setMinimumWidth(390)
        self._cancel_requested = False
        self._build_ui()
        self._load_range()

    def _spin(self, value, minimum=0.0, maximum=1.0, step=0.05, decimals=3):
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setDecimals(decimals)
        widget.setValue(value)
        return widget

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        note = QtWidgets.QLabel("親→子の連続したノードを選択して実行します。ローカルX軸が子方向を向くリグを想定しています。")
        note.setWordWrap(True)
        root.addWidget(note)

        build_label = QtWidgets.QLabel(f"ビルド: {BUILD}  /  Maya 2025以降  /  PySide6")
        root.addWidget(build_label)

        spring_group = QtWidgets.QGroupBox("スプリング")
        form = QtWidgets.QFormLayout(spring_group)
        self.spring_value = self._spin(0.7)
        self.twist_value = self._spin(0.7)
        self.tension_value = self._spin(0.5)
        self.extend_value = self._spin(0.0)
        self.inertia_value = self._spin(0.0)
        self.subdiv_value = QtWidgets.QSpinBox()
        self.subdiv_value.setRange(1, 20)
        self.subdiv_value.setValue(1)
        form.addRow("スプリング", self.spring_value)
        form.addRow("ねじれ", self.twist_value)
        form.addRow("張力", self.tension_value)
        form.addRow("しなり", self.extend_value)
        form.addRow("慣性", self.inertia_value)
        form.addRow("サブフレーム", self.subdiv_value)
        self.include_root_check = QtWidgets.QCheckBox("ルート骨も計算")
        self.include_root_check.setChecked(False)
        self.include_root_check.setToolTip("オフ: 最上位のルート骨はドライバとして固定 / オン: ルート骨からスプリング・風・当たり判定を計算")
        form.addRow(self.include_root_check)
        self.include_branch_check = QtWidgets.QCheckBox("分岐骨も計算")
        self.include_branch_check.setChecked(True)
        self.include_branch_check.setToolTip("オン: 選択階層の分岐点になっている骨自身も計算 / オフ: 分岐骨を固定して各枝だけ計算（016互換）")
        form.addRow(self.include_branch_check)
        root.addWidget(spring_group)

        range_group = QtWidgets.QGroupBox("キー設定")
        range_layout = QtWidgets.QGridLayout(range_group)
        self.active_range = QtWidgets.QCheckBox("アニメーション範囲を使用")
        self.active_range.setChecked(True)
        self.start_frame = QtWidgets.QSpinBox()
        self.end_frame = QtWidgets.QSpinBox()
        for widget in (self.start_frame, self.end_frame):
            widget.setRange(-100000, 100000)
        self.loop_check = QtWidgets.QCheckBox("ループ")
        self.pose_match_check = QtWidgets.QCheckBox("ポーズ合わせ")
        self.wipe_sub_check = QtWidgets.QCheckBox("サブフレームキーを削除")
        self.wipe_sub_check.setChecked(True)
        range_layout.addWidget(self.active_range, 0, 0, 1, 2)
        range_layout.addWidget(QtWidgets.QLabel("開始"), 1, 0)
        range_layout.addWidget(self.start_frame, 1, 1)
        range_layout.addWidget(QtWidgets.QLabel("終了"), 2, 0)
        range_layout.addWidget(self.end_frame, 2, 1)
        range_layout.addWidget(self.loop_check, 3, 0)
        range_layout.addWidget(self.pose_match_check, 3, 1)
        range_layout.addWidget(self.wipe_sub_check, 4, 0, 1, 2)
        self.active_range.toggled.connect(self._range_mode_changed)
        root.addWidget(range_group)

        col_group = QtWidgets.QGroupBox("当たり判定")
        col_layout = QtWidgets.QGridLayout(col_group)
        self.collision_check = QtWidgets.QCheckBox("衝突判定を有効化")
        self.collision_margin = self._spin(0.0, 0.0, 1000.0, 0.1, 3)
        self.collision_margin.setToolTip("衝突物をこの値だけ外側へ膨らませて判定します。めり込みが気になる場合に少し増やしてください。")
        self.collision_recovery_stiffness = self._spin(0.8, 0.01, 1.0, 0.05, 3)
        self.collision_recovery_stiffness.setToolTip(
            "衝突後に元のSpring軌道へ戻る速さです。小さいほど柔らかくゆっくり戻り、1.0でほぼ即座に戻ります。"
        )
        self.collision_chain_follow = self._spin(0.65, 0.0, 1.0, 0.05, 3)
        self.collision_chain_follow.setToolTip(
            "関節付近の衝突で1本だけが急に折れないよう、下位骨の向きへ上位骨も連動させる強さです。"
            "0.0で従来挙動、1.0で強く連動します。"
        )
        add_sphere = QtWidgets.QPushButton("球作成")
        add_box = QtWidgets.QPushButton("ボックス作成")
        clear_collision = QtWidgets.QPushButton("衝突物を削除")
        add_sphere.clicked.connect(self._add_sphere)
        add_box.clicked.connect(self._add_box)
        clear_collision.clicked.connect(self._clear_collision)
        col_layout.addWidget(self.collision_check, 0, 0, 1, 2)
        col_layout.addWidget(QtWidgets.QLabel("当たり余白"), 1, 0)
        col_layout.addWidget(self.collision_margin, 1, 1)
        col_layout.addWidget(QtWidgets.QLabel("復帰の固さ"), 2, 0)
        col_layout.addWidget(self.collision_recovery_stiffness, 2, 1)
        col_layout.addWidget(QtWidgets.QLabel("関節連動"), 3, 0)
        col_layout.addWidget(self.collision_chain_follow, 3, 1)
        col_layout.addWidget(add_sphere, 4, 0)
        col_layout.addWidget(add_box, 4, 1)
        col_layout.addWidget(clear_collision, 5, 0, 1, 2)
        root.addWidget(col_group)

        wind_group = QtWidgets.QGroupBox("風")
        wind_layout = QtWidgets.QFormLayout(wind_group)
        self.wind_enable = QtWidgets.QCheckBox("風を有効化")
        self.wind_enable.setChecked(False)
        self.wind_enable.setToolTip("オフなら、シーンに風オブジェクトが残っていても計算には使用しません。")
        self.wind_max = self._spin(100.0, -1000.0, 1000.0, 0.1)
        self.wind_min = self._spin(0.5, -1000.0, 1000.0, 0.1)
        self.wind_freq = self._spin(1.0, 0.0, 100.0, 0.1)
        self.wind_freq.setToolTip("1.0で約30フレームに1周期です。骨ごとに少し位相をずらしてなびかせます。")
        self.wind_tip = self._spin(2.5, 1.0, 10.0, 0.1, 2)
        self.wind_tip.setToolTip("先端ほど風を強く受ける倍率です。1.0で均一、値を上げるほど毛先・先端が大きくなびきます。")
        wind_button = QtWidgets.QPushButton("風オブジェクト作成 / 値更新")
        wind_button.clicked.connect(self._set_wind)
        wind_layout.addRow(self.wind_enable)
        wind_layout.addRow("最大風力", self.wind_max)
        wind_layout.addRow("最小風力", self.wind_min)
        wind_layout.addRow("周波数", self.wind_freq)
        wind_layout.addRow("先端なびき倍率", self.wind_tip)
        wind_layout.addRow(wind_button)
        wind_note = QtWidgets.QLabel("円錐の先端方向（ローカルY+）が風向きです。")
        wind_note.setWordWrap(True)
        wind_layout.addRow(wind_note)
        root.addWidget(wind_group)

        gravity_group = QtWidgets.QGroupBox("重力")
        gravity_layout = QtWidgets.QFormLayout(gravity_group)
        self.gravity_enable = QtWidgets.QCheckBox("重力を有効化")
        self.gravity_enable.setChecked(False)
        self.gravity_enable.setToolTip("オフなら、シーンに重力オブジェクトが残っていても計算には使用しません。")
        self.gravity_strength = self._spin(1.0, -1000.0, 1000.0, 0.1)
        gravity_button = QtWidgets.QPushButton("重力オブジェクト作成 / 値更新")
        gravity_button.clicked.connect(self._set_gravity)
        gravity_layout.addRow(self.gravity_enable)
        gravity_layout.addRow("重力の強さ", self.gravity_strength)
        gravity_layout.addRow(gravity_button)
        gravity_note = QtWidgets.QLabel("円錐の先端方向（ローカルY+）が重力方向です。")
        gravity_note.setWordWrap(True)
        gravity_layout.addRow(gravity_note)
        root.addWidget(gravity_group)

        angle_group = QtWidgets.QGroupBox("基準角度")
        angle_layout = QtWidgets.QHBoxLayout(angle_group)
        save_angle_button = QtWidgets.QPushButton("角度を保存")
        restore_angle_button = QtWidgets.QPushButton("保存角度に戻す")
        clear_angle_button = QtWidgets.QPushButton("保存角度を解除")
        save_angle_button.clicked.connect(self._save_angles)
        restore_angle_button.clicked.connect(self._restore_angles)
        clear_angle_button.clicked.connect(self._clear_angles)
        angle_layout.addWidget(save_angle_button)
        angle_layout.addWidget(restore_angle_button)
        angle_layout.addWidget(clear_angle_button)
        root.addWidget(angle_group)

        pose_group = QtWidgets.QGroupBox("骨ポーズ")
        pose_layout = QtWidgets.QHBoxLayout(pose_group)
        copy_button = QtWidgets.QPushButton("コピー")
        paste_button = QtWidgets.QPushButton("貼り付け")
        straight_button = QtWidgets.QPushButton("直線化")
        copy_button.clicked.connect(self._copy_pose)
        paste_button.clicked.connect(self._paste_pose)
        straight_button.clicked.connect(self._straighten)
        pose_layout.addWidget(copy_button)
        pose_layout.addWidget(paste_button)
        pose_layout.addWidget(straight_button)
        root.addWidget(pose_group)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QtWidgets.QLabel("待機中")
        self.status.setWordWrap(True)
        root.addWidget(self.progress)
        root.addWidget(self.status)

        buttons = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("適用")
        self.apply_button.setMinimumHeight(34)
        self.cancel_button = QtWidgets.QPushButton("キャンセル")
        self.cancel_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.cancel_button.clicked.connect(self._request_cancel)
        buttons.addWidget(self.apply_button, 1)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)

        for button in self.findChildren(QtWidgets.QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    def _load_range(self):
        try:
            self.start_frame.setValue(int(cmds.playbackOptions(q=True, min=True)))
            self.end_frame.setValue(int(cmds.playbackOptions(q=True, max=True)))
        except Exception:
            self.start_frame.setValue(0)
            self.end_frame.setValue(100)
        self._range_mode_changed(self.active_range.isChecked())

    def _range_mode_changed(self, active):
        self.start_frame.setEnabled(not active)
        self.end_frame.setEnabled(not active)

    def _effective_range(self):
        if self.active_range.isChecked():
            return (
                int(cmds.playbackOptions(q=True, min=True)),
                int(cmds.playbackOptions(q=True, max=True)),
            )
        return self.start_frame.value(), self.end_frame.value()

    def _request_cancel(self):
        self._cancel_requested = True
        self.status.setText("キャンセル要求中...")

    def _progress_callback(self, value, message=None):
        self.progress.setValue(int(round(value)))
        if message:
            self.status.setText(message)
        QtWidgets.QApplication.processEvents()
        return not self._cancel_requested

    def _run_small_action(self, func, success_text):
        try:
            result = func()
            if callable(success_text):
                success_text = success_text(result)
            self.status.setText(success_text)
        except Exception as exc:
            self.status.setText(f"エラー: {exc}")
            traceback.print_exc()

    def _add_sphere(self):
        self._run_small_action(core.create_collision_sphere, lambda result: f"球を{len(result)}個作成しました。")

    def _add_box(self):
        self._run_small_action(core.create_collision_box, lambda result: f"ボックスを{len(result)}個作成しました。")

    def _clear_collision(self):
        self._run_small_action(core.remove_collision_helpers, lambda count: f"衝突物を{count}個削除しました。")

    def _set_wind(self):
        def action():
            return core.set_wind_values(
                self.wind_max.value(), self.wind_min.value(),
                self.wind_freq.value(), self.wind_tip.value(),
            )
        self._run_small_action(action, "風を設定しました。コーンの先端方向（ローカルY+）が風向きです。")
        self.wind_enable.setChecked(True)

    def _set_gravity(self):
        def action():
            return core.set_gravity_value(self.gravity_strength.value())
        self._run_small_action(action, "重力を設定しました。円錐の先端方向（ローカルY+）が重力方向です。")
        self.gravity_enable.setChecked(True)

    def _save_angles(self):
        self._run_small_action(
            core.save_reference_angles,
            lambda count: f"{count}ノードの角度を基準角度として保存しました。",
        )

    def _restore_angles(self):
        self._run_small_action(
            core.restore_reference_angles,
            lambda count: f"{count}ノードを保存角度へ戻しました。",
        )

    def _clear_angles(self):
        self._run_small_action(
            core.clear_reference_angles,
            lambda count: f"{count}ノードの保存角度を解除しました。",
        )

    def _copy_pose(self):
        self._run_small_action(core.copy_pose, lambda count: f"{count}ノードの姿勢をコピーしました。")

    def _paste_pose(self):
        self._run_small_action(core.paste_pose, lambda count: f"{count}ノードへ姿勢を貼り付けました。")

    def _straighten(self):
        self._run_small_action(core.straighten_selected, lambda count: f"{count}ノードを子方向へ整列しました。")

    def _apply(self):
        start_frame, end_frame = self._effective_range()

        try:
            if self.wind_enable.isChecked():
                core.sync_existing_wind_values(
                    self.wind_max.value(), self.wind_min.value(),
                    self.wind_freq.value(), self.wind_tip.value(),
                )
            if self.gravity_enable.isChecked():
                core.sync_existing_gravity_value(self.gravity_strength.value())
        except Exception as exc:
            self.status.setText(f"エラー: {exc}")
            return

        spring = core.Spring(
            ratio=1.0 - self.spring_value.value(),
            twist_ratio=1.0 - self.twist_value.value(),
            tension=self.tension_value.value(),
            extend=self.extend_value.value(),
            inertia=self.inertia_value.value(),
        )
        settings = core.SpringMagicSettings(
            start_frame=start_frame,
            end_frame=end_frame,
            sub_div=self.subdiv_value.value(),
            is_loop=self.loop_check.isChecked(),
            is_pose_match=self.pose_match_check.isChecked(),
            is_collision=self.collision_check.isChecked(),
            collision_margin=self.collision_margin.value(),
            collision_recovery_stiffness=self.collision_recovery_stiffness.value(),
            collision_chain_follow=self.collision_chain_follow.value(),
            include_root=self.include_root_check.isChecked(),
            include_branch_points=self.include_branch_check.isChecked(),
            wipe_subframe=self.wipe_sub_check.isChecked(),
            use_wind=self.wind_enable.isChecked(),
            use_gravity=self.gravity_enable.isChecked(),
        )

        self._cancel_requested = False
        self.apply_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("計算を開始します...")
        QtWidgets.QApplication.processEvents()

        cmds.undoInfo(openChunk=True)
        try:
            core.start_compute(spring, settings, self._progress_callback)
            self.status.setText("完了しました。問題があればCtrl+Zで戻せます。")
        except core.CancelledError:
            self.status.setText("キャンセルしました。必要ならCtrl+Zで計算前へ戻してください。")
        except Exception as exc:
            self.status.setText(f"エラー: {exc}")
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(self, "SpringMaya", str(exc))
        finally:
            cmds.undoInfo(closeChunk=True)
            self.apply_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress.setValue(0)


def show():
    global _WINDOW

    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "SpringMayaDialog":
                    widget.close()
                    widget.deleteLater()
    except Exception:
        pass

    try:
        if _WINDOW is not None:
            _WINDOW.close()
            _WINDOW.deleteLater()
    except Exception:
        pass
        
    _WINDOW = SpringMayaDialog()
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW

show()