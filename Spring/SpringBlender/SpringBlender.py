# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""SpringBlender Ver0.1 / Blender 5.2+

SpringMax 018 / SpringMaya 003 を基準にした、単一ファイルのBlenderアドオン。
3Dビュー > サイドバー > SpringBlender から使用します。
"""

VERSION = (0, 1, 0)
VERSION_TEXT = ".".join(str(part) for part in VERSION[:2])

bl_info = {
    "name": "SpringBlender",
    "author": "DiGiMonkey",
    "version": VERSION,
    "blender": (5, 2, 0),
    "location": "3D View > Sidebar > SpringBlender",
    "description": "選択したボーンチェーンにスプリング、風、重力、衝突をベイクします",
    "doc_url": "https://github.com/cgtc11/Script_3D/Spring",
    "tracker_url": "https://github.com/cgtc11/Script_3D/issues",
    "category": "Animation",
}

import math
import traceback
from collections import OrderedDict

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

EPS = 1.0e-8
TYPE_PROP = "SpringMagicType"
SPHERE_TAG = "SpringMagicSphere"
BOX_TAG = "SpringMagicBox"
WIND_TAG = "SpringMagicWind"
GRAVITY_TAG = "SpringMagicGravity"
ANGLE_SAVED_PROP = "SM_AngleSaved"

_ANGLE_REFERENCE = {}
_POSE_CLIPBOARD = {}


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def sigmoid(value):
    return 1.0 / (1.0 + math.exp(-value))


def _safe_normalized(value, fallback=None):
    value = Vector(value)
    if value.length_squared > EPS * EPS:
        return value.normalized()
    return Vector(fallback or (0.0, 0.0, 0.0))


def _set_frame(scene, value):
    base = math.floor(float(value) + 1.0e-7)
    subframe = float(value) - base
    scene.frame_set(int(base), subframe=max(0.0, min(0.999999, subframe)))


def _active_armature(context, require_pose=True):
    obj = context.object
    if obj is None or obj.type != 'ARMATURE':
        raise ValueError("アーマチュアをアクティブにしてください。")
    if require_pose and context.mode != 'POSE':
        raise ValueError("アーマチュアをポーズモードにしてください。")
    return obj


def _selected_pose_bones(context):
    armature = _active_armature(context)
    selected = list(context.selected_pose_bones or [])
    if not selected:
        raise ValueError("計算する親子ボーンをポーズモードで選択してください。")
    return armature, selected


def _handle(bone):
    return (bone.id_data.name_full, bone.name)


def _valid_bone(bone):
    try:
        obj = bone.id_data
        return obj is not None and obj.name in bpy.data.objects and bone.name in obj.pose.bones
    except (ReferenceError, AttributeError):
        return False


def _world_matrix(bone):
    return bone.id_data.matrix_world @ bone.matrix


def _set_world_matrix(bone, matrix):
    bone.matrix = bone.id_data.matrix_world.inverted_safe() @ matrix
    bpy.context.view_layer.update()


def _world_position(bone):
    return _world_matrix(bone).translation.copy()


def _world_tail(bone):
    return bone.id_data.matrix_world @ bone.tail


def _world_axis(bone, index):
    return _safe_normalized(_world_matrix(bone).to_3x3().col[index])


def _object_world_axis(obj, index):
    return _safe_normalized(obj.matrix_world.to_3x3().col[index])


def _set_world_aim_y(bone, target, up_vector, reference_up=None, continuity_up=None):
    """Aim Blender bone local Y at target while stabilizing local Z roll."""
    position = _world_position(bone)
    y_axis = _safe_normalized(target - position)
    if y_axis.length_squared < EPS:
        return False

    reference_up = _safe_normalized(reference_up or _world_axis(bone, 2))
    continuity_up = _safe_normalized(continuity_up or _world_axis(bone, 2))
    desired_up = _safe_normalized(up_vector)

    def projected(axis):
        projected_axis = axis - y_axis * axis.dot(y_axis)
        return _safe_normalized(projected_axis)

    desired_z = projected(desired_up)
    reference_z = projected(reference_up)
    continuity_z = projected(continuity_up)
    parallel = abs(desired_up.dot(y_axis)) if desired_up.length_squared > EPS else 1.0

    if parallel > 0.965 and continuity_z.length_squared > EPS:
        z_axis = continuity_z
    elif desired_z.length_squared > EPS:
        z_axis = desired_z
        if continuity_z.length_squared > EPS and z_axis.dot(continuity_z) < 0.0:
            z_axis.negate()
        if continuity_z.length_squared > EPS:
            z_axis = _safe_normalized(z_axis * 0.82 + continuity_z * 0.18)
    elif continuity_z.length_squared > EPS:
        z_axis = continuity_z
    elif reference_z.length_squared > EPS:
        z_axis = reference_z
    else:
        fallback = Vector((0.0, 0.0, 1.0)) if abs(y_axis.z) < 0.9 else Vector((1.0, 0.0, 0.0))
        z_axis = projected(fallback)

    if z_axis.length_squared < EPS:
        return False
    if reference_z.length_squared > EPS and z_axis.dot(reference_z) < -0.25:
        z_axis.negate()

    x_axis = _safe_normalized(y_axis.cross(z_axis))
    if x_axis.length_squared < EPS:
        return False
    z_axis = _safe_normalized(x_axis.cross(y_axis))

    current = _world_matrix(bone)
    scale = current.to_scale()
    rotation = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    desired = Matrix.Translation(position) @ rotation @ Matrix.Diagonal((*scale, 1.0))
    _set_world_matrix(bone, desired)
    return True


def _basis_components_in_parent(bone, axis):
    axis = _safe_normalized(axis)
    if bone.parent is None:
        return axis.copy(), None
    px, py, pz = (_world_axis(bone.parent, i) for i in range(3))
    return Vector((axis.dot(px), axis.dot(py), axis.dot(pz))), _handle(bone.parent)


def _capture_angle_reference(bone):
    axes = []
    parent_handle = None
    for index in range(3):
        local, parent_handle = _basis_components_in_parent(bone, _world_axis(bone, index))
        axes.append(local)
    return {"parent_handle": parent_handle, "x": axes[0], "y": axes[1], "z": axes[2]}


def _reference_world_axis(bone, reference, key):
    local = Vector(reference[key])
    if bone.parent is None or reference.get("parent_handle") is None:
        return _safe_normalized(local)
    px, py, pz = (_world_axis(bone.parent, i) for i in range(3))
    return _safe_normalized(px * local.x + py * local.y + pz * local.z)


def _persist_angle_reference(bone, reference):
    bone[ANGLE_SAVED_PROP] = True
    bone["SM_AngleHasParent"] = reference.get("parent_handle") is not None
    for key in ("x", "y", "z"):
        bone["SM_Angle_" + key.upper()] = list(reference[key])


def _load_angle_reference(bone):
    if not bool(bone.get(ANGLE_SAVED_PROP, False)):
        return None
    try:
        axes = {key: Vector(bone["SM_Angle_" + key.upper()]) for key in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None
    if axes["y"].length_squared < EPS or axes["z"].length_squared < EPS:
        return None
    return {
        "parent_handle": (0, 0) if bool(bone.get("SM_AngleHasParent", False)) else None,
        **axes,
    }


def _saved_angle_reference(bone):
    reference = _ANGLE_REFERENCE.get(_handle(bone))
    if reference is None:
        reference = _load_angle_reference(bone)
        if reference is not None:
            _ANGLE_REFERENCE[_handle(bone)] = reference
    return reference


def _bone_depth(bone):
    depth, current = 0, bone.parent
    while current is not None:
        depth += 1
        current = current.parent
    return depth


def _rotation_data_path(bone):
    if bone.rotation_mode == 'QUATERNION':
        return "rotation_quaternion"
    if bone.rotation_mode == 'AXIS_ANGLE':
        return "rotation_axis_angle"
    return "rotation_euler"


def _insert_transform_key(bone, frame, include_scale=False):
    bone.keyframe_insert(data_path=_rotation_data_path(bone), frame=float(frame), group=bone.name)
    if include_scale:
        bone.keyframe_insert(data_path="scale", frame=float(frame), group=bone.name)


def _channelbag_for_object(obj):
    animation = obj.animation_data
    if animation is None or animation.action is None or animation.action_slot is None:
        return None
    return anim_utils.action_get_channelbag_for_slot(animation.action, animation.action_slot)


def _remove_keys(bone, start_frame, end_frame, include_scale=False, non_integer_only=False):
    bag = _channelbag_for_object(bone.id_data)
    if bag is None:
        return
    paths = {bone.path_from_id(_rotation_data_path(bone))}
    if include_scale:
        paths.add(bone.path_from_id("scale"))
    for curve in bag.fcurves:
        if curve.data_path not in paths:
            continue
        removed = False
        for point in list(curve.keyframe_points):
            frame = float(point.co.x)
            in_range = start_frame - 1.0e-6 <= frame <= end_frame + 1.0e-6
            wanted = in_range and (not non_integer_only or abs(frame - round(frame)) > 1.0e-5)
            if wanted:
                curve.keyframe_points.remove(point, fast=True)
                removed = True
        if removed:
            curve.update()


def _selected_chain_paths(bones, include_root=False, include_branch_points=True):
    selected = {_handle(bone): bone for bone in bones}

    def selected_children(bone):
        return [child for child in bone.children if _handle(child) in selected]

    def branch_reference_child(bone, children):
        direction = _world_axis(bone, 1)
        origin = _world_position(bone)
        return max(children, key=lambda child: _safe_normalized(_world_position(child) - origin).dot(direction))

    roots = [bone for bone in bones if bone.parent is None or _handle(bone.parent) not in selected]
    paths, visited = [], set()

    def walk(start, is_selection_root=False):
        if _handle(start) in visited:
            return
        visited.add(_handle(start))
        path, current = [start], start
        while len(selected_children(current)) == 1:
            current = selected_children(current)[0]
            path.append(current)
        branches = selected_children(current)
        stored = list(path)
        if len(branches) > 1 and include_branch_points:
            stored.append(branch_reference_child(current, branches))
        if not include_root and is_selection_root and start.parent is None and len(stored) > 1:
            stored = stored[1:]
        if len(stored) >= 2:
            paths.append(stored)
        if len(branches) > 1:
            for child in branches:
                walk(child)

    for root in roots:
        walk(root, True)
    if not paths:
        raise ValueError("計算できる親子チェーンがありません。各枝で親子ボーンを連続選択してください。")
    return paths


class Spring:
    def __init__(self, ratio, twist_ratio, tension, extend, inertia):
        self.ratio = float(ratio)
        self.twist_ratio = float(twist_ratio)
        self.tension = float(tension)
        self.extend = float(extend)
        self.inertia = float(inertia)


class SolverSettings:
    def __init__(self, props):
        self.start_frame = int(props.start_frame)
        self.end_frame = int(props.end_frame)
        self.sub_div = max(1, int(props.sub_div))
        self.is_loop = bool(props.is_loop)
        self.is_pose_match = bool(props.is_pose_match)
        self.is_collision = bool(props.is_collision)
        self.collision_margin = max(0.0, float(props.collision_margin))
        self.collision_recovery_stiffness = clamp(props.collision_recovery_stiffness, 0.01, 1.0)
        self.collision_chain_follow = clamp(props.collision_chain_follow, 0.0, 1.0)
        self.include_root = bool(props.include_root)
        self.include_branch_points = bool(props.include_branch_points)
        self.wipe_subframe = bool(props.wipe_subframe)
        self.use_wind = bool(props.use_wind)
        self.use_gravity = bool(props.use_gravity)
        self.wind = None
        self.gravity = None


class SpringData:
    def __init__(self, settings, spring, parent, child, grand_child, grand_parent, chain_index, chain_count):
        self.settings = settings
        self.spring = spring
        self.parent = parent
        self.child = child
        self.grand_child = grand_child
        self.grand_parent = grand_parent
        self.chain_index = chain_index
        self.chain_count = max(1, chain_count)
        self.child_position = _world_position(child)
        self.previous_child_position = self.child_position.copy()
        self.grand_child_position = _world_position(grand_child) if grand_child else None
        self.stable_up_axis = _world_axis(parent, 2)
        self.bone_length = max(EPS, (self.child_position - _world_position(parent)).length)
        self.start_parent_matrix = _world_matrix(parent).copy()
        self.start_scale = parent.scale.copy()
        saved = _saved_angle_reference(parent)
        self.angle_reference = saved or _capture_angle_reference(parent)
        self.has_child_collide = False
        self.contact_active = False
        self.collision_recovery_active = False
        self.collision_recovery_position = self.child_position.copy()
        self.collision_recovery_parent_position = _world_position(parent)
        self.pose_samples = {}

    def sample_pose(self, frame):
        self.pose_samples[round(float(frame), 6)] = (_world_position(self.child), _world_axis(self.parent, 2))

    def reference_axis(self, key):
        return _reference_world_axis(self.parent, self.angle_reference, key)

    def natural_target(self, frame):
        sample = self.pose_samples.get(round(float(frame), 6))
        if sample is not None:
            return sample[0].copy()
        direction = self.reference_axis("y")
        if direction.length_squared < EPS:
            direction = _world_axis(self.parent, 1)
        return _world_position(self.parent) + direction * self.bone_length

    def update(self, collision_active, corrected):
        self.child_position = _world_position(self.child)
        self.previous_child_position = Vector(corrected)
        if self.grand_child and _valid_bone(self.grand_child):
            self.grand_child_position = _world_position(self.grand_child)
        self.stable_up_axis = _world_axis(self.parent, 2)
        self.has_child_collide = bool(collision_active)

    def sync_final_pose(self):
        self.child_position = _world_position(self.child)
        self.previous_child_position = self.child_position.copy()
        self.stable_up_axis = _world_axis(self.parent, 2)

    def recovery_target(self, parent_pos, natural):
        if not self.collision_recovery_active:
            return natural.copy(), False
        delta = parent_pos - self.collision_recovery_parent_position
        previous = self.collision_recovery_position + delta
        alpha = 1.0 - math.pow(1.0 - self.settings.collision_recovery_stiffness, 1.0 / self.settings.sub_div)
        candidate = previous.lerp(natural, alpha)
        candidate = _keep_length(parent_pos, candidate, self.bone_length, natural - parent_pos)
        self.collision_recovery_position = candidate.copy()
        self.collision_recovery_parent_position = parent_pos.copy()
        if (candidate - natural).length <= max(1.0e-4, self.bone_length * 1.0e-4):
            self.collision_recovery_active = False
            return natural.copy(), False
        return candidate, True

    def begin_recovery(self, parent_pos, corrected):
        self.collision_recovery_active = True
        self.collision_recovery_position = corrected.copy()
        self.collision_recovery_parent_position = parent_pos.copy()

    def apply_inertia(self, current):
        ratio = self.spring.ratio / self.settings.sub_div
        offset = Vector()
        if self.spring.inertia > 0.0:
            reference = current - self.child_position
            if reference.length_squared > EPS:
                distance = (reference * (1.0 - ratio) * (1.0 - self.spring.inertia)).length
                offset = reference.normalized() * (distance / self.settings.sub_div)
        force = self.child_position - self.previous_child_position
        if force.length_squared > EPS:
            offset += force.normalized() * (force.length * self.spring.inertia / self.settings.sub_div)
        return offset

    def apply_wind(self, frame, natural):
        wind = self.settings.wind
        if wind is None:
            return Vector()
        maximum = float(wind.get("MaxForce", 100.0))
        minimum = float(wind.get("MinForce", 0.5))
        frequency = max(0.0, float(wind.get("Frequency", 1.0)))
        tip = clamp(float(wind.get("TipMultiplier", 2.5)), 1.0, 10.0)
        direction = _object_world_axis(wind, 2)
        phase = frame * frequency * (2.0 * math.pi / 30.0) - self.chain_index * 0.55
        force = minimum + (maximum - minimum) * (math.sin(phase) + 1.0) * 0.5
        if abs(force) < EPS:
            return Vector()
        parent_pos = _world_position(self.parent)
        bone_axis = _safe_normalized(natural - parent_pos, self.reference_axis("y"))
        target_direction = direction if force >= 0.0 else -direction
        depth = (self.chain_index + 1.0) / self.chain_count
        gain = 1.0 + (tip - 1.0) * math.pow(depth, 1.35)
        bend = clamp(1.0 - math.exp(-abs(force) * 0.004 * gain), 0.0, 0.94)
        desired = _safe_normalized(bone_axis * (1.0 - bend) + target_direction * bend)
        return parent_pos + desired * self.bone_length - natural

    def apply_gravity(self):
        gravity = self.settings.gravity
        if gravity is None:
            return Vector()
        return _object_world_axis(gravity, 2) * (float(gravity.get("Strength", 1.0)) / self.settings.sub_div)

    def compute_up(self, frame):
        sample = self.pose_samples.get(round(float(frame), 6))
        current = sample[1] if sample is not None else self.reference_axis("z")
        previous = self.stable_up_axis
        ratio = self.spring.twist_ratio / self.settings.sub_div
        up = _safe_normalized(previous * (1.0 - ratio) + current * ratio, current)
        reference = self.reference_axis("z")
        anchor = 1.0 - math.pow(0.78, 1.0 / self.settings.sub_div)
        if reference.length_squared > EPS:
            if up.dot(reference) < 0.0:
                up.negate()
            up = _safe_normalized(up * (1.0 - anchor) + reference * anchor)
        return up

    def aim_by_ratio(self, up, new_target, corrected):
        ratio = self.spring.ratio / self.settings.sub_div
        tension = self.spring.tension / (1.0 / (sigmoid(1.0 - self.settings.sub_div) + 0.5))
        target = corrected * (1.0 - ratio) + new_target * ratio
        if self.has_child_collide and self.grand_child_position is not None and tension > 0.0:
            weight = (1.0 - ratio) * tension
            target = (target + self.grand_child_position * weight) / (1.0 + weight)
        _set_world_aim_y(self.parent, target, up, self.reference_axis("z"), self.stable_up_axis)

    def extend_bone(self, corrected):
        if abs(self.spring.extend) < EPS:
            return
        desired = (_world_position(self.parent) - corrected).length
        factor = (self.bone_length * (1.0 - self.spring.extend) + desired * self.spring.extend) / self.bone_length
        self.parent.scale.y = self.start_scale.y * max(EPS, factor)


def _helpers(tag):
    return [obj for obj in bpy.context.scene.objects if obj.get(TYPE_PROP, "") == tag]


def _helper_scale(obj):
    matrix = obj.matrix_world.to_3x3()
    return Vector((matrix.col[0].length, matrix.col[1].length, matrix.col[2].length)) * obj.empty_display_size


def _sphere_data(obj):
    scale = _helper_scale(obj)
    return obj.matrix_world.translation.copy(), max(EPS, max(scale))


def _box_data(obj):
    center = obj.matrix_world.translation.copy()
    axes = tuple(_object_world_axis(obj, i) for i in range(3))
    return center, axes, _helper_scale(obj)


def _keep_length(parent, candidate, length, fallback):
    direction = _safe_normalized(candidate - parent, fallback)
    if direction.length_squared < EPS:
        direction = Vector((0.0, 1.0, 0.0))
    return parent + direction * length


def _tangent(normal, bone_direction):
    bone = _safe_normalized(bone_direction)
    normal = _safe_normalized(normal)
    tangent = normal - bone * normal.dot(bone)
    if tangent.length_squared > EPS:
        return tangent.normalized()
    reference = Vector((0.0, 0.0, 1.0)) if abs(bone.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    return _safe_normalized(bone.cross(reference), (1.0, 0.0, 0.0))


def _closest_on_segment(point, start, end):
    axis = end - start
    if axis.length_squared < EPS:
        return start.copy(), 0.0
    t = clamp((point - start).dot(axis) / axis.length_squared, 0.0, 1.0)
    return start + axis * t, t


def _obb_local(point, center, axes):
    delta = point - center
    return Vector((delta.dot(axes[0]), delta.dot(axes[1]), delta.dot(axes[2])))


def _inside_box(point, center, axes, half):
    local = _obb_local(point, center, axes)
    return all(abs(local[i]) < half[i] for i in range(3))


def _box_escape(point, center, axes, half, bone_direction):
    p = _obb_local(point, center, axes)
    candidates = [
        (half.x - p.x, axes[0]), (half.x + p.x, -axes[0]),
        (half.y - p.y, axes[1]), (half.y + p.y, -axes[1]),
        (half.z - p.z, axes[2]), (half.z + p.z, -axes[2]),
    ]
    bone = _safe_normalized(bone_direction)
    scored = []
    for penetration, normal in candidates:
        tangent = normal - bone * normal.dot(bone)
        scored.append((max(0.0, penetration) / max(0.02, tangent.length), penetration, normal, tangent))
    _, penetration, normal, tangent = min(scored, key=lambda item: item[0])
    return _safe_normalized(tangent, _tangent(normal, bone)), max(0.0, penetration)


def _segment_box_interval(start, end, center, axes, half):
    a, b = _obb_local(start, center, axes), _obb_local(end, center, axes)
    direction = b - a
    minimum, maximum = 0.0, 1.0
    for origin, delta, extent in zip(a, direction, half):
        if abs(delta) < EPS:
            if origin < -extent or origin > extent:
                return False, None, None
            continue
        t1, t2 = (-extent - origin) / delta, (extent - origin) / delta
        if t1 > t2:
            t1, t2 = t2, t1
        minimum, maximum = max(minimum, t1), min(maximum, t2)
        if minimum > maximum:
            return False, None, None
    return True, minimum, maximum


def _resolve_sphere(parent, child, center, radius, length, fallback, skin):
    result, changed = child.copy(), False
    bone_direction = _safe_normalized(result - parent)
    target = radius + skin
    delta = result - center
    if delta.length < target:
        normal = _safe_normalized(delta, parent - center)
        result = _keep_length(parent, result + _tangent(normal, bone_direction) * max(target - delta.length, skin), length, fallback)
        changed = True
        bone_direction = _safe_normalized(result - parent)
    if (parent - center).length < target:
        return changed, result
    closest, lever = _closest_on_segment(center, parent, result)
    delta = closest - center
    if delta.length < target:
        normal = _safe_normalized(delta, parent - center)
        push = _tangent(normal, bone_direction) * (max(target - delta.length, skin) / max(0.12, lever))
        result = _keep_length(parent, result + push, length, fallback)
        changed = True
    return changed, result


def _resolve_box(parent, child, center, axes, half, length, fallback, skin):
    result, changed = child.copy(), False
    inflated = half + Vector((skin, skin, skin))
    bone_direction = _safe_normalized(result - parent)
    if _inside_box(result, center, axes, inflated):
        tangent, penetration = _box_escape(result, center, axes, inflated, bone_direction)
        result = _keep_length(parent, result + tangent * max(penetration + skin, skin), length, fallback)
        changed = True
    if _inside_box(parent, center, axes, inflated):
        return changed, result
    hit, enter, leave = _segment_box_interval(parent, result, center, axes, inflated)
    if hit:
        lever = clamp((enter + leave) * 0.5, 0.0, 1.0)
        point = parent + (result - parent) * lever
        tangent, penetration = _box_escape(point, center, axes, inflated, bone_direction)
        result = _keep_length(parent, result + tangent * (max(penetration + skin, skin) / max(0.12, lever)), length, fallback)
        changed = True
    return changed, result


def _resolve_child(parent, child, spheres, boxes, margin, iterations=40):
    if not spheres and not boxes:
        return False, child
    length = (child - parent).length
    if length < EPS:
        return False, child
    result, collided = child.copy(), False
    fallback = _safe_normalized(child - parent)
    skin = max(1.0e-3, max(0.0, margin) * 0.05)
    for _ in range(iterations):
        changed = False
        for obj in spheres:
            center, radius = _sphere_data(obj)
            hit, result = _resolve_sphere(parent, result, center, radius + margin, length, fallback, skin)
            changed |= hit
            collided |= hit
        for obj in boxes:
            center, axes, half = _box_data(obj)
            half += Vector((margin, margin, margin))
            hit, result = _resolve_box(parent, result, center, axes, half, length, fallback, skin)
            changed |= hit
            collided |= hit
        if not changed:
            break
    return collided, result


def _strict_resolve_pose(data, spheres, boxes, up):
    if not data.settings.is_collision:
        return False
    collided = False
    for _ in range(10):
        hit, target = _resolve_child(
            _world_position(data.parent), _world_position(data.child), spheres, boxes,
            data.settings.collision_margin,
        )
        if not hit:
            break
        collided = True
        if not _set_world_aim_y(data.parent, target, up, data.reference_axis("z"), data.stable_up_axis):
            break
    return collided


def _detect_collision(data, parent, desired, spheres, boxes):
    if not data.settings.is_collision or (not spheres and not boxes):
        data.collision_recovery_active = False
        return False, False, desired, data.child_position.copy()
    candidate, recovering = data.recovery_target(parent, desired)
    hit, target = _resolve_child(parent, candidate, spheres, boxes, data.settings.collision_margin, 24)
    if hit:
        data.begin_recovery(parent, target)
        return True, True, target, target.copy()
    if recovering:
        return False, True, candidate, candidate.copy()
    return False, False, desired, data.child_position.copy()


def _chain_follow(chains, spheres, boxes):
    if not chains or (not spheres and not boxes):
        return False
    strength = chains[0][0].settings.collision_chain_follow
    if strength <= EPS:
        return False
    iterations = 3
    alpha = 1.0 - math.pow(1.0 - strength, 1.0 / (chains[0][0].settings.sub_div * iterations))
    changed = False
    for _ in range(iterations):
        for chain in chains:
            flags = [data.contact_active for data in chain]
            for index in range(len(chain) - 2, -1, -1):
                if not flags[index + 1]:
                    continue
                upper, lower = chain[index], chain[index + 1]
                parent, joint, tip = _world_position(upper.parent), _world_position(upper.child), _world_position(lower.child)
                upper_dir, lower_dir = _safe_normalized(joint - parent), _safe_normalized(tip - joint)
                dot = clamp(upper_dir.dot(lower_dir), -1.0, 1.0)
                straight = math.cos(math.radians(25.0))
                bend = clamp((straight - dot) / straight, 0.0, 1.0) if dot < straight else 0.0
                desired = _safe_normalized(upper_dir * (1.0 - alpha * bend) + _safe_normalized(tip - parent) * alpha * bend)
                if bend > EPS and _set_world_aim_y(upper.parent, parent + desired * upper.bone_length, upper.compute_up(0), upper.reference_axis("z"), upper.stable_up_axis):
                    changed = True
                    flags[index] = True
        for chain in chains:
            for data in chain:
                if _strict_resolve_pose(data, spheres, boxes, data.compute_up(0)):
                    data.contact_active = True
                    corrected = _world_position(data.child)
                    data.begin_recovery(_world_position(data.parent), corrected)
                    changed = True
    return changed


def _run_solver(context, props):
    scene = context.scene
    armature, selected = _selected_pose_bones(context)
    settings = SolverSettings(props)
    if settings.end_frame <= settings.start_frame:
        raise ValueError("終了フレームは開始フレームより後にしてください。")
    spring = Spring(props.spring, props.twist, props.tension, props.flex, props.inertia)
    paths = _selected_chain_paths(selected, settings.include_root, settings.include_branch_points)
    original_frame = scene.frame_current_final
    original_selection = [bone.name for bone in selected]
    data_by_handle, chains = OrderedDict(), []

    settings.wind = next(iter(_helpers(WIND_TAG)), None) if settings.use_wind else None
    settings.gravity = next(iter(_helpers(GRAVITY_TAG)), None) if settings.use_gravity else None
    spheres = _helpers(SPHERE_TAG) if settings.is_collision else []
    boxes = _helpers(BOX_TAG) if settings.is_collision else []
    wm = context.window_manager
    wm.progress_begin(0, 100)
    try:
        _set_frame(scene, settings.start_frame)
        for path in paths:
            chain = []
            for index, parent in enumerate(path[:-1]):
                child = path[index + 1]
                data = SpringData(
                    settings, spring, parent, child,
                    path[index + 2] if index + 2 < len(path) else None,
                    parent.parent, index, len(path) - 1,
                )
                data_by_handle[_handle(parent)] = data
                chain.append(data)
            if chain:
                chains.append(chain)

        if settings.is_pose_match:
            total = settings.end_frame - settings.start_frame + 1
            for offset, frame in enumerate(range(settings.start_frame, settings.end_frame + 1)):
                _set_frame(scene, frame)
                for data in data_by_handle.values():
                    data.sample_pose(frame)
                wm.progress_update((offset + 1) * 15.0 / max(1, total))

        for data in data_by_handle.values():
            _remove_keys(data.parent, settings.start_frame, settings.end_frame, abs(spring.extend) > EPS)

        _set_frame(scene, settings.start_frame)
        for data in data_by_handle.values():
            _set_world_matrix(data.parent, data.start_parent_matrix)
            data.parent.scale = data.start_scale
            _insert_transform_key(data.parent, settings.start_frame, abs(spring.extend) > EPS)

        step = 1.0 / settings.sub_div
        frames = []
        frame = settings.start_frame + step
        while frame <= settings.end_frame + 1.0e-6:
            frames.append(frame)
            frame += step
        if settings.is_loop:
            frame = float(settings.start_frame)
            while frame <= settings.end_frame + 1.0e-6:
                frames.append(frame)
                frame += step

        progress_start = 15.0 if settings.is_pose_match else 0.0
        for frame_index, frame in enumerate(frames):
            _set_frame(scene, frame)
            for data in data_by_handle.values():
                parent_pos = _world_position(data.parent)
                natural = data.natural_target(frame)
                desired = natural + data.apply_inertia(natural) + data.apply_wind(frame, natural) + data.apply_gravity()
                hit, active, desired, corrected = _detect_collision(data, parent_pos, desired, spheres, boxes)
                up = data.compute_up(frame)
                data.aim_by_ratio(up, desired, corrected)
                if _strict_resolve_pose(data, spheres, boxes, up):
                    hit = active = True
                    corrected = _world_position(data.child)
                    data.begin_recovery(_world_position(data.parent), corrected)
                data.extend_bone(corrected)
                data.contact_active = bool(hit)
                data.update(active, corrected)
            if settings.is_collision and _chain_follow(chains, spheres, boxes):
                for data in data_by_handle.values():
                    data.sync_final_pose()
            for data in data_by_handle.values():
                _insert_transform_key(data.parent, frame, abs(spring.extend) > EPS)
            progress = progress_start + (frame_index + 1) * (100.0 - progress_start) / max(1, len(frames))
            wm.progress_update(progress)

        if settings.wipe_subframe and settings.sub_div > 1:
            for data in data_by_handle.values():
                _remove_keys(data.parent, settings.start_frame, settings.end_frame, abs(spring.extend) > EPS, True)

        _set_frame(scene, settings.end_frame)
    finally:
        wm.progress_end()
        for bone in armature.pose.bones:
            bone.select = bone.name in original_selection
        if not data_by_handle:
            _set_frame(scene, original_frame)


def _new_helper(context, tag, name, display_type):
    obj = bpy.data.objects.new(name, None)
    context.collection.objects.link(obj)
    obj.empty_display_type = display_type
    obj.empty_display_size = 1.0
    obj.location = context.scene.cursor.location
    if context.object is not None:
        obj.matrix_world.translation = context.object.matrix_world.translation
    obj[TYPE_PROP] = tag
    obj.show_in_front = True
    for selected in context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


class SpringBlenderProperties(PropertyGroup):
    spring: FloatProperty(name="スプリング", default=0.30, min=0.0, max=1.0)
    twist: FloatProperty(name="ねじれ", default=0.30, min=0.0, max=1.0)
    tension: FloatProperty(name="張力", default=0.50, min=0.0, max=1.0)
    flex: FloatProperty(name="しなり", default=0.0, min=0.0, max=1.0)
    inertia: FloatProperty(name="慣性", default=0.0, min=0.0, max=1.0)
    start_frame: IntProperty(name="開始", default=1)
    end_frame: IntProperty(name="終了", default=250)
    sub_div: IntProperty(name="サブフレーム", default=1, min=1, max=16)
    is_loop: BoolProperty(name="ループ", default=False)
    is_pose_match: BoolProperty(name="ポーズ合わせ", default=False)
    wipe_subframe: BoolProperty(name="計算後サブフレームキーを削除", default=True)
    include_root: BoolProperty(name="ルート骨も計算", default=False)
    include_branch_points: BoolProperty(name="分岐骨も計算", default=True)
    is_collision: BoolProperty(name="当たり判定", default=False)
    collision_margin: FloatProperty(name="当たり余白", default=0.0, min=0.0)
    collision_recovery_stiffness: FloatProperty(name="復帰の固さ", default=0.15, min=0.01, max=1.0)
    collision_chain_follow: FloatProperty(name="関節連動", default=0.65, min=0.0, max=1.0)
    use_wind: BoolProperty(name="風を使用", default=False)
    use_gravity: BoolProperty(name="重力を使用", default=False)
    wind_max: FloatProperty(name="最大風力", default=100.0)
    wind_min: FloatProperty(name="最小風力", default=0.5)
    wind_frequency: FloatProperty(name="周波数", default=1.0, min=0.0)
    wind_tip: FloatProperty(name="先端なびき倍率", default=2.5, min=1.0, max=10.0)
    gravity_strength: FloatProperty(name="重力", default=1.0)


class SPRINGBLENDER_OT_apply(Operator):
    bl_idname = "spring_blender.apply"
    bl_label = "適用"
    bl_description = "選択した親子ボーンへスプリングをベイクします"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'ARMATURE' and context.mode == 'POSE'

    def execute(self, context):
        try:
            _run_solver(context, context.scene.spring_blender)
        except Exception as exc:
            traceback.print_exc()
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, "SpringBlender: 計算が完了しました。")
        return {'FINISHED'}


class SPRINGBLENDER_OT_save_angles(Operator):
    bl_idname = "spring_blender.save_angles"
    bl_label = "角度を保存"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            _, bones = _selected_pose_bones(context)
            for bone in bones:
                reference = _capture_angle_reference(bone)
                _ANGLE_REFERENCE[_handle(bone)] = reference
                _persist_angle_reference(bone, reference)
            self.report({'INFO'}, f"{len(bones)}本の角度を保存しました。")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class SPRINGBLENDER_OT_restore_angles(Operator):
    bl_idname = "spring_blender.restore_angles"
    bl_label = "保存角度に戻す"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            _, bones = _selected_pose_bones(context)
            bones = sorted((b for b in bones if _saved_angle_reference(b)), key=_bone_depth)
            for bone in bones:
                reference = _saved_angle_reference(bone)
                target = _world_position(bone) + _reference_world_axis(bone, reference, "y")
                _set_world_aim_y(bone, target, _reference_world_axis(bone, reference, "z"))
            self.report({'INFO'}, f"{len(bones)}本を保存角度へ戻しました。")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class SPRINGBLENDER_OT_clear_angles(Operator):
    bl_idname = "spring_blender.clear_angles"
    bl_label = "保存角度を解除"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            _, bones = _selected_pose_bones(context)
            for bone in bones:
                _ANGLE_REFERENCE.pop(_handle(bone), None)
                bone[ANGLE_SAVED_PROP] = False
            self.report({'INFO'}, f"{len(bones)}本の保存角度を解除しました。")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class SPRINGBLENDER_OT_copy_pose(Operator):
    bl_idname = "spring_blender.copy_pose"
    bl_label = "ポーズをコピー"
    def execute(self, context):
        try:
            armature, bones = _selected_pose_bones(context)
            _POSE_CLIPBOARD.clear()
            _POSE_CLIPBOARD.update({(armature.name_full, bone.name): bone.matrix_basis.copy() for bone in bones})
            self.report({'INFO'}, f"{len(bones)}本のポーズをコピーしました。")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class SPRINGBLENDER_OT_paste_pose(Operator):
    bl_idname = "spring_blender.paste_pose"
    bl_label = "ポーズを貼り付け"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            armature, bones = _selected_pose_bones(context)
            count = 0
            for bone in sorted(bones, key=_bone_depth):
                matrix = _POSE_CLIPBOARD.get((armature.name_full, bone.name))
                if matrix is not None:
                    bone.matrix_basis = matrix.copy(); count += 1
            context.view_layer.update()
            self.report({'INFO'}, f"{count}本へ貼り付けました。")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class SPRINGBLENDER_OT_straighten(Operator):
    bl_idname = "spring_blender.straighten"
    bl_label = "選択骨をまっすぐにする"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        try:
            _, bones = _selected_pose_bones(context)
            count = 0
            for bone in sorted(bones, key=_bone_depth):
                children = [child for child in bone.children if child.select]
                if children:
                    _set_world_aim_y(bone, _world_position(children[0]), _world_axis(bone, 2)); count += 1
            self.report({'INFO'}, f"{count}本を整列しました。")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class SPRINGBLENDER_OT_create_sphere(Operator):
    bl_idname = "spring_blender.create_sphere"
    bl_label = "球を作成"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        _new_helper(context, SPHERE_TAG, "SpringCollisionSphere", 'SPHERE')
        return {'FINISHED'}


class SPRINGBLENDER_OT_create_box(Operator):
    bl_idname = "spring_blender.create_box"
    bl_label = "BOXを作成"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        _new_helper(context, BOX_TAG, "SpringCollisionBox", 'CUBE')
        return {'FINISHED'}


class SPRINGBLENDER_OT_remove_colliders(Operator):
    bl_idname = "spring_blender.remove_colliders"
    bl_label = "当たり判定を削除"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        objects = _helpers(SPHERE_TAG) + _helpers(BOX_TAG)
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        self.report({'INFO'}, f"{len(objects)}個を削除しました。")
        return {'FINISHED'}


class SPRINGBLENDER_OT_create_wind(Operator):
    bl_idname = "spring_blender.create_wind"
    bl_label = "風を作成"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props = context.scene.spring_blender
        obj = _new_helper(context, WIND_TAG, "SpringWind", 'SINGLE_ARROW')
        obj["MaxForce"], obj["MinForce"] = props.wind_max, props.wind_min
        obj["Frequency"], obj["TipMultiplier"] = props.wind_frequency, props.wind_tip
        return {'FINISHED'}


class SPRINGBLENDER_OT_sync_wind(Operator):
    bl_idname = "spring_blender.sync_wind"
    bl_label = "風の値を反映"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props, objects = context.scene.spring_blender, _helpers(WIND_TAG)
        for obj in objects:
            obj["MaxForce"], obj["MinForce"] = props.wind_max, props.wind_min
            obj["Frequency"], obj["TipMultiplier"] = props.wind_frequency, props.wind_tip
        self.report({'INFO'}, f"{len(objects)}個の風へ反映しました。")
        return {'FINISHED'}


class SPRINGBLENDER_OT_create_gravity(Operator):
    bl_idname = "spring_blender.create_gravity"
    bl_label = "重力を作成"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj = _new_helper(context, GRAVITY_TAG, "SpringGravity", 'SINGLE_ARROW')
        obj["Strength"] = context.scene.spring_blender.gravity_strength
        return {'FINISHED'}


class SPRINGBLENDER_OT_sync_gravity(Operator):
    bl_idname = "spring_blender.sync_gravity"
    bl_label = "重力の値を反映"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        objects = _helpers(GRAVITY_TAG)
        for obj in objects:
            obj["Strength"] = context.scene.spring_blender.gravity_strength
        self.report({'INFO'}, f"{len(objects)}個の重力へ反映しました。")
        return {'FINISHED'}


class SPRINGBLENDER_PT_main(Panel):
    bl_label = "SpringBlender Ver0.1"
    bl_idname = "SPRINGBLENDER_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SpringBlender"

    def draw(self, context):
        layout, props = self.layout, context.scene.spring_blender
        layout.label(text=f"製作者: DiGiMonkey / Ver{VERSION_TEXT}")
        layout.label(text="Blender 5.2以降")
        link = layout.operator("wm.url_open", text="GitHub: Script_3D / Spring", icon='URL')
        link.url = "https://github.com/cgtc11/Script_3D/Spring"
        box = layout.box(); box.label(text="スプリング")
        for name in ("spring", "twist", "tension", "flex", "inertia"):
            box.prop(props, name)
        row = box.row(align=True); row.prop(props, "start_frame"); row.prop(props, "end_frame")
        box.prop(props, "sub_div"); box.prop(props, "wipe_subframe")
        row = box.row(align=True); row.prop(props, "is_loop"); row.prop(props, "is_pose_match")
        box.prop(props, "include_root"); box.prop(props, "include_branch_points")

        box = layout.box(); box.label(text="基準姿勢")
        row = box.row(align=True); row.operator("spring_blender.save_angles"); row.operator("spring_blender.restore_angles")
        box.operator("spring_blender.clear_angles")
        row = box.row(align=True); row.operator("spring_blender.copy_pose"); row.operator("spring_blender.paste_pose")
        box.operator("spring_blender.straighten")

        box = layout.box(); box.prop(props, "is_collision")
        column = box.column(); column.enabled = props.is_collision
        column.prop(props, "collision_margin"); column.prop(props, "collision_recovery_stiffness"); column.prop(props, "collision_chain_follow")
        row = column.row(align=True); row.operator("spring_blender.create_sphere"); row.operator("spring_blender.create_box")
        column.operator("spring_blender.remove_colliders")

        box = layout.box(); box.prop(props, "use_wind")
        column = box.column(); column.enabled = props.use_wind
        for name in ("wind_max", "wind_min", "wind_frequency", "wind_tip"):
            column.prop(props, name)
        row = column.row(align=True); row.operator("spring_blender.create_wind"); row.operator("spring_blender.sync_wind")

        box = layout.box(); box.prop(props, "use_gravity")
        column = box.column(); column.enabled = props.use_gravity
        column.prop(props, "gravity_strength")
        row = column.row(align=True); row.operator("spring_blender.create_gravity"); row.operator("spring_blender.sync_gravity")
        layout.separator(); layout.operator("spring_blender.apply", icon='PLAY')


CLASSES = (
    SpringBlenderProperties,
    SPRINGBLENDER_OT_apply,
    SPRINGBLENDER_OT_save_angles,
    SPRINGBLENDER_OT_restore_angles,
    SPRINGBLENDER_OT_clear_angles,
    SPRINGBLENDER_OT_copy_pose,
    SPRINGBLENDER_OT_paste_pose,
    SPRINGBLENDER_OT_straighten,
    SPRINGBLENDER_OT_create_sphere,
    SPRINGBLENDER_OT_create_box,
    SPRINGBLENDER_OT_remove_colliders,
    SPRINGBLENDER_OT_create_wind,
    SPRINGBLENDER_OT_sync_wind,
    SPRINGBLENDER_OT_create_gravity,
    SPRINGBLENDER_OT_sync_gravity,
    SPRINGBLENDER_PT_main,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.spring_blender = PointerProperty(type=SpringBlenderProperties)


def unregister():
    if hasattr(bpy.types.Scene, "spring_blender"):
        del bpy.types.Scene.spring_blender
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()
