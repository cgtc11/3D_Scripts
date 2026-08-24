# -*- coding: utf-8 -*-
"""SpringMax 025 / 3ds Max 2025以降 / PySide6

単一ファイル版。3ds Max の「スクリプト > スクリプトを実行」からこのファイルだけを実行できます。
"""

from __future__ import print_function

import math
import sys
import traceback
from collections import OrderedDict

from PySide6 import QtCore, QtWidgets
import pymxs
from pymxs import runtime as rt

try:
    from qtmax import GetQMaxMainWindow
except Exception:
    GetQMaxMainWindow = None

BUILD = "025"

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

    def __repr__(self):
        return "Vec3({0:.6f}, {1:.6f}, {2:.6f})".format(self.x, self.y, self.z)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def distance(a, b):
    return (b - a).length()


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


PROXY_SUFFIX = "_SpringNull_MAX"
SPHERE_TAG = "SpringMagicSphere"
BOX_TAG = "SpringMagicBox"
# Legacy tags are retained only so the delete button can clean helpers made by 005 and earlier.
LEGACY_CAPSULE_TAG = "SpringMagicCapsule"
LEGACY_PLANE_TAG = "SpringMagicPlane"
WIND_TAG = "SpringMagicWind"
GRAVITY_TAG = "SpringMagicGravity"
TYPE_PROP = "SpringMagicType"


def _install_maxscript_helpers():
    # PyMXS has no arbitrary `in coordsys <matrix3>` context.  Keep these helpers
    # deliberately tiny and isolated so all simulation math remains in Python.
    rt.execute(
        r"""
        fn SpringMagicMAX_SetWorldRotationSafe theNode worldTM =
        (
            local worldPos = theNode.transform.translationPart
            local worldRot = inverse worldTM.rotationPart
            in coordsys (transmatrix worldPos) theNode.rotation = worldRot
        )
        """
    )

    # Euler smoothing is an extra safety pass.  If a future controller/plugin
    # environment does not expose the expected Euler classes, the main solver
    # must still start normally.
    try:
        rt.execute(
            r"""
            fn SpringMagicMAX_SmoothEulerKeys theNode startF endF =
            (
                local rotCtrl = getPropertyController theNode.controller #rotation
                if rotCtrl == undefined then return false
                local cls = classof rotCtrl
                if (cls != Euler_XYZ and cls != Local_Euler_XYZ) then return false
                if (isProperty rotCtrl #axisOrder) and rotCtrl.axisOrder != 1 then return false

                local qs = #()
                for f = startF to endF do
                (
                    at time f append qs rotCtrl.value
                )
                if qs.count < 2 then return false

                local smooth = quatArrayToEulerArray qs
                if smooth.count != qs.count then return false

                with animate on
                (
                    for i = 1 to smooth.count do
                    (
                        local f = startF + i - 1
                        local ea = smooth[i]
                        at time f
                        (
                            rotCtrl.x_rotation = ea.x
                            rotCtrl.y_rotation = ea.y
                            rotCtrl.z_rotation = ea.z
                        )
                    )
                )
                true
            )
            """
        )
    except Exception:
        pass


_install_maxscript_helpers()


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
        collision_recovery_stiffness=0.15,
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
        # 0.01 = very soft/slow return, 1.0 = immediate return.
        # Kept above zero so a recovery can never remain frozen forever.
        self.collision_recovery_stiffness = clamp(float(collision_recovery_stiffness), 0.01, 1.0)
        # 0.0 keeps the old per-bone collision response. Larger values let an
        # upstream joint rotate toward the already-corrected lower bone so a
        # collision at a joint is shared by the chain instead of being dumped
        # into one very sharp bend.
        self.collision_chain_follow = clamp(float(collision_chain_follow), 0.0, 1.0)
        self.include_root = bool(include_root)
        self.include_branch_points = bool(include_branch_points)
        self.wipe_subframe = bool(wipe_subframe)
        self.use_wind = bool(use_wind)
        self.use_gravity = bool(use_gravity)
        self.wind = None
        self.gravity = None


def _point(v):
    v = Vec3.from_value(v)
    return rt.Point3(v.x, v.y, v.z)


def _vec(v):
    return Vec3.from_value(v)


def _copy_matrix(tm):
    try:
        return rt.copy(tm)
    except Exception:
        return rt.matrix3(tm.row1, tm.row2, tm.row3, tm.row4)


def _node_handle(node):
    return int(rt.getHandleByAnim(node))


def _valid_node(node):
    try:
        return bool(rt.isValidNode(node))
    except Exception:
        return node is not None


def _enter_world_coords():
    try:
        previous = rt.getRefCoordSys()
    except Exception:
        previous = None
    try:
        rt.setRefCoordSys(rt.Name("world"))
    except Exception:
        pass
    return previous


def _restore_coords(previous):
    if previous is None:
        return
    try:
        rt.setRefCoordSys(previous)
    except Exception:
        # #object / picked coordinate systems cannot always be restored through setRefCoordSys().
        pass


def _parent(node):
    try:
        p = node.parent
        if p is None or str(p) == "undefined":
            return None
        return p
    except Exception:
        return None


def _children(node):
    try:
        return [child for child in node.children]
    except Exception:
        return []


def _world_matrix(node):
    return node.transform


def _world_position(node):
    return _vec(_world_matrix(node).row4)


def _world_axis(node, row_index):
    tm = _world_matrix(node)
    row = (tm.row1, tm.row2, tm.row3)[row_index]
    return _vec(row).normalized()


def _matrix_scale(tm):
    return Vec3(_vec(tm.row1).length(), _vec(tm.row2).length(), _vec(tm.row3).length())


def _set_world_rotation_from_matrix(node, world_tm):
    """Set world orientation without orbiting the node around the world origin.

    MAXScript's node.rotation is interpreted in the active coordinate system.
    Using #world directly can rotate the node around the scene origin and move a
    bone hierarchy apart.  Also, Matrix3.rotationPart uses 3ds Max's internal
    matrix rotation convention, so it must be inverted before assigning it to
    node.rotation.

    PyMXS does not expose the arbitrary ``in coordsys <matrix3>`` context, so a
    tiny MAXScript helper is used for the exact operation recommended by the
    MAXScript documentation: rotate in a coordinate system translated to the
    node's own world position.
    """
    try:
        rt.SpringMagicMAX_SetWorldRotationSafe(node, world_tm)
    except Exception:
        # Fallback: applying the complete world TM keeps the pivot position
        # intact.  This path is only used if the helper could not be installed.
        node.transform = _copy_matrix(world_tm)


def _set_world_rotation_from_basis(node, x_axis, y_axis, z_axis, position=None):
    old_tm = _world_matrix(node)
    scale = _matrix_scale(old_tm)
    if position is None:
        position = _vec(old_tm.row4)
    new_tm = rt.matrix3(
        _point(x_axis.normalized() * (scale.x if scale.x > EPS else 1.0)),
        _point(y_axis.normalized() * (scale.y if scale.y > EPS else 1.0)),
        _point(z_axis.normalized() * (scale.z if scale.z > EPS else 1.0)),
        _point(position),
    )
    _set_world_rotation_from_matrix(node, new_tm)


def _aim_x_axis(node, target, up_vector, reference_up=None, continuity_up=None):
    """Aim local X at target without introducing one-frame roll flips.

    The 010 solver could still "twitch" when the requested up vector became
    almost parallel to the new X axis.  In that condition the projected Y axis
    is nearly zero, so tiny floating-point changes can choose a different
    orientation branch on the next frame.  012 parallel-transports the previous
    frame's Y axis and only then blends toward the desired/reference up vector.
    """
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

    # Near the pole, do not let an almost-zero desired projection determine
    # the roll.  Keep the previous frame's hemisphere instead.
    parallel_amount = abs(desired_up.dot(x_axis)) if not desired_up.is_zero() else 1.0
    if parallel_amount > 0.965 and not continuity_y.is_zero():
        y_axis = continuity_y
    elif not desired_y.is_zero():
        y_axis = desired_y
        if not continuity_y.is_zero() and y_axis.dot(continuity_y) < 0.0:
            y_axis = -y_axis
        # Small continuity blend suppresses one-frame numerical jumps without
        # making normal twist response feel sticky.
        if not continuity_y.is_zero():
            y_axis = (y_axis * 0.82 + continuity_y * 0.18).normalized()
    elif not continuity_y.is_zero():
        y_axis = continuity_y
    elif not ref_y.is_zero():
        y_axis = ref_y
    else:
        fallback = Vec3(0.0, 0.0, 1.0) if abs(x_axis.z) < 0.9 else Vec3(0.0, 1.0, 0.0)
        y_axis = projected(fallback)

    if y_axis.is_zero():
        return False

    # The saved/start reference is used only as a hemisphere guard here.
    # This avoids a sudden 180-degree branch switch while still allowing twist.
    if not ref_y.is_zero() and y_axis.dot(ref_y) < -0.25:
        y_axis = -y_axis

    z_axis = x_axis.cross(y_axis).normalized()
    if z_axis.is_zero():
        return False
    y_axis = z_axis.cross(x_axis).normalized()
    _set_world_rotation_from_basis(node, x_axis, y_axis, z_axis, obj_pos)
    return True


def _unique_scene_name(base):
    if rt.getNodeByName(base) is None:
        return base
    index = 1
    while True:
        name = "{0}_{1:03d}".format(base, index)
        if rt.getNodeByName(name) is None:
            return name
        index += 1


def _set_type(node, value):
    rt.setUserPropVal(node, TYPE_PROP, value, quoteStrings=True)


def _get_type(node):
    try:
        value = rt.getUserPropVal(node, TYPE_PROP, asString=True)
        if value is None or str(value) == "undefined":
            return ""
        return str(value).strip('"')
    except Exception:
        try:
            value = rt.getUserProp(node, TYPE_PROP)
            return "" if value is None else str(value).strip('"')
        except Exception:
            return ""


def _scene_nodes_by_type(value):
    result = []
    for node in rt.objects:
        if _get_type(node) == value:
            result.append(node)
    return result



# Saved reference angles live for the current 3ds Max/Python session.  The
# reference is stored in the node parent's coordinate basis rather than world
# space, so the saved shape follows an animated/moving rig root.
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
    # If the hierarchy has changed since the angle was saved, fall back to the
    # current parent basis.  The important property is a stable local angle.
    px = _world_axis(parent, 0)
    py = _world_axis(parent, 1)
    pz = _world_axis(parent, 2)
    world = px * local.x + py * local.y + pz * local.z
    return world.normalized()


def _persist_angle_reference(node, reference):
    rt.setUserPropVal(node, "SpringMagicAngleSaved", True)
    rt.setUserPropVal(node, "SpringMagicAngleHasParent", reference.get("parent_handle") is not None)
    for key in ("x", "y", "z"):
        value = reference[key]
        rt.setUserPropVal(node, "SpringMagicAngle_{0}X".format(key.upper()), float(value.x))
        rt.setUserPropVal(node, "SpringMagicAngle_{0}Y".format(key.upper()), float(value.y))
        rt.setUserPropVal(node, "SpringMagicAngle_{0}Z".format(key.upper()), float(value.z))


def _read_user_prop(node, key, default=None):
    try:
        value = rt.getUserPropVal(node, key)
        if value is None or str(value) == "undefined":
            return default
        return value
    except Exception:
        return default


def _load_persisted_angle_reference(node):
    if not bool(_read_user_prop(node, "SpringMagicAngleSaved", False)):
        return None
    has_parent = bool(_read_user_prop(node, "SpringMagicAngleHasParent", False))
    axes = {}
    try:
        for key in ("x", "y", "z"):
            prefix = "SpringMagicAngle_{0}".format(key.upper())
            axes[key] = Vec3(
                float(_read_user_prop(node, prefix + "X", 0.0)),
                float(_read_user_prop(node, prefix + "Y", 0.0)),
                float(_read_user_prop(node, prefix + "Z", 0.0)),
            )
    except Exception:
        return None
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
    for node in rt.selection:
        reference = _capture_angle_reference(node)
        _ANGLE_REFERENCE[_node_handle(node)] = reference
        _persist_angle_reference(node, reference)
        count += 1
    return count


def clear_reference_angles():
    count = 0
    for node in rt.selection:
        handle = _node_handle(node)
        had_reference = handle in _ANGLE_REFERENCE or _saved_angle_reference(node) is not None
        _ANGLE_REFERENCE.pop(handle, None)
        try:
            rt.setUserPropVal(node, "SpringMagicAngleSaved", False)
        except Exception:
            pass
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
    nodes = [n for n in rt.selection if _saved_angle_reference(n) is not None]
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
    rt.redrawViews()
    return count


def _select_nodes(nodes):
    try:
        rt.clearSelection()
    except Exception:
        pass
    first = True
    for node in nodes:
        if not _valid_node(node):
            continue
        try:
            if first:
                rt.select(node)
                first = False
            else:
                rt.selectMore(node)
        except Exception:
            pass


def _delete_key_range(controller, start_frame, end_frame):
    if controller is None:
        return
    try:
        rt.deselectKeys(controller)
        rt.selectKeys(controller, rt.interval(start_frame, end_frame))
        rt.deleteKeys(controller, rt.Name("selection"))
    except Exception:
        pass


def _rotation_controller(node):
    try:
        return rt.getPropertyController(node.controller, "Rotation")
    except Exception:
        return None


def _position_controller(node):
    try:
        return rt.getPropertyController(node.controller, "Position")
    except Exception:
        return None


def _delete_rotation_keys(node, start_frame, end_frame):
    _delete_key_range(_rotation_controller(node), start_frame, end_frame)


def _delete_position_keys(node, start_frame, end_frame):
    _delete_key_range(_position_controller(node), start_frame, end_frame)


def _delete_non_integer_keys(animatable, start_frame, end_frame, _visited=None):
    if animatable is None:
        return
    if _visited is None:
        _visited = set()
    try:
        key = int(rt.getHandleByAnim(animatable))
    except Exception:
        key = id(animatable)
    if key in _visited:
        return
    _visited.add(key)

    try:
        supports_keys = bool(animatable.supportsKeys)
    except Exception:
        supports_keys = False

    if supports_keys:
        try:
            keys = animatable.keys
            for index in range(len(keys), 0, -1):
                # pymxs collection access is Python 0-based, while deleteKey() takes a 1-based index.
                key_obj = keys[index - 1]
                frame = float(key_obj.time.frame)
                if start_frame - 1e-5 <= frame <= end_frame + 1e-5 and abs(frame - round(frame)) > 1e-5:
                    rt.deleteKey(animatable, index)
        except Exception:
            pass

    try:
        sub_count = int(animatable.numSubs)
    except Exception:
        sub_count = 0
    for index in range(1, sub_count + 1):
        try:
            sub = rt.getSubAnim(animatable, index)
            try:
                controller = rt.getProperty(sub, "controller")
            except Exception:
                controller = None
            if controller is not None:
                _delete_non_integer_keys(controller, start_frame, end_frame, _visited)
        except Exception:
            continue


def _smooth_euler_rotation_keys(node, start_frame, end_frame):
    """Unwrap standard XYZ Euler keys after solving to prevent isolated flips.

    3ds Max can represent the same quaternion orientation with multiple Euler
    triples.  When a different representation is chosen on one frame, the bone
    can visibly "twitch" even though the intended world orientation is smooth.
    Autodesk exposes quatArrayToEulerArray specifically to generate a continuous
    Euler sequence.  The MAXScript helper applies it only to standard XYZ Euler
    controllers; other controller types are left untouched.
    """
    try:
        return bool(rt.SpringMagicMAX_SmoothEulerKeys(node, int(start_frame), int(end_frame)))
    except Exception:
        return False



def _selected_chain_paths(nodes, include_root=False, include_branch_points=True):
    """選択ノードから、分岐を含む複数の直列チェーンを作る。

    017では「分岐骨も計算」がONなら、分岐点自身も1回だけ計算対象にする。
    分岐骨には複数の選択子があるため、計算用の子はその骨のローカルX軸に
    最も沿う子を1個だけ参照する。各枝そのものは従来通り独立チェーンとして
    再帰処理するため、分岐骨を複数回回転させることはない。

    OFFの場合は016互換で、分岐点は固定基準として各子から先だけを計算する。
    「ルート骨も計算」はこの設定とは独立しており、ワールド直下の最上位骨を
    計算するかどうかだけを制御する。
    """
    if not nodes:
        return []

    selected_by_handle = {_node_handle(node): node for node in nodes}
    selected_handles = set(selected_by_handle.keys())

    def selected_children(node):
        return [c for c in _children(node) if _node_handle(c) in selected_handles]

    def branch_reference_child(node, children):
        """分岐骨自身の向きを決めるため、ローカルX軸に最も沿う子を選ぶ。"""
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
                # 子のピボットがBone終端にある通常のMax Boneでは、この値が
                # ほぼ1になる。手動で枝位置をずらしている場合も最も自然な子を選ぶ。
                score = delta.normalized().dot(x_axis)
            if score > best_score:
                best_score = score
                best_child = child
        return best_child

    # 選択範囲の先頭。互いに接続していない複数の選択群にも対応する。
    roots = []
    for node in nodes:
        p = _parent(node)
        if p is None or _node_handle(p) not in selected_handles:
            roots.append(node)

    paths = []
    visited_starts = set()

    def walk_linear(start, is_selection_root=False):
        start_handle = _node_handle(start)
        # 同じ枝を重複生成しないための保険。
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

        # 017: 分岐骨自身も計算する場合は、分岐骨のローカルX軸に最も沿う
        # 子を「終端参照」として1つだけ追加する。SpringDataはpath[:-1]を
        # 計算するため、これでcurrent（分岐骨）がちょうど1回だけ対象になる。
        stored_path = list(path)
        if len(branch_children) > 1 and include_branch_points:
            reference_child = branch_reference_child(current, branch_children)
            if reference_child is not None:
                stored_path.append(reference_child)

        # 従来互換: ワールド直下の選択ルートはデフォルトではドライバ扱い。
        # 「ルート骨も計算」がONのときだけ、そのルート自身も計算対象にする。
        if (
            not include_root
            and is_selection_root
            and _parent(start) is None
            and len(stored_path) > 1
        ):
            stored_path = stored_path[1:]

        if len(stored_path) >= 2:
            paths.append(stored_path)

        # 分岐後は各子から先を独立チェーンとして処理する。
        # 分岐骨自身を計算する場合でも、ここでは子から開始するため
        # 同じ分岐骨が枝ごとに重複計算されることはない。
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
    name = _unique_scene_name("{0}{1}".format(parent_node.name, PROXY_SUFFIX))
    proxy = rt.Point(name=name, size=1.0, cross=False, box=True, axistripod=False)
    proxy.transform = _copy_matrix(child_node.transform)
    p = _parent(parent_node)
    if p is not None:
        proxy.parent = p
        proxy.transform = _copy_matrix(child_node.transform)
    try:
        rt.hide(proxy)
    except Exception:
        pass
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
        # 014: 先端ほど強く、かつ少し遅れて風を受けるためのチェーン情報。
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
        self.start_parent_transform = _copy_matrix(parent_node.transform)
        self.start_child_transform = _copy_matrix(child_node.transform)
        saved_reference = _saved_angle_reference(parent_node)
        self.reference_is_saved = saved_reference is not None
        self.angle_reference = saved_reference if saved_reference is not None else _capture_angle_reference(parent_node)
        self.has_child_collide = False
        self.collision_active = False
        # True only while actually touching a collision helper.  Recovery is a
        # separate state; chain-follow must not keep pulling ancestors after the
        # contact itself has ended.
        self.contact_active = False

        # Collision recovery state.  006 returned to the unconstrained Spring
        # target immediately on the first non-colliding sample, which could
        # produce a visible snap.  007 keeps the last collision-corrected child
        # target and eases it back toward the normal trajectory.
        self.collision_recovery_active = False
        self.collision_recovery_position = self.child_position.copy()
        self.collision_recovery_parent_position = _world_position(parent_node)

    def sample_proxy(self, frame):
        self.proxy.transform = _copy_matrix(self.child.transform)

    def reference_axis(self, key):
        return _reference_world_axis(self.parent, self.angle_reference, key)

    def natural_target(self):
        """Return the absolute rest target for this bone.

        012 deliberately does not use the helper/proxy position as the rest
        target.  That allowed collision/chain corrections to leave the bone on
        a different trajectory.  Every sample now has one authoritative local
        reference angle: the saved angle when present, otherwise the angle at
        the moment Apply was pressed.  Because the reference is stored in the
        parent basis, the rest shape still follows an animated/moving rig root.
        """
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
        """Synchronize pose caches without destroying the recovery trajectory.

        011 overwrote ``collision_recovery_position`` after the chain-follow
        pass.  While a descendant was recovering this effectively moved the
        recovery start point every frame and could keep the chain bent forever.
        012 keeps the recovery anchor intact; parent motion is already handled
        by ``recovery_target()`` through ``collision_recovery_parent_position``.
        """
        self.child_position = _world_position(self.child)
        if self.grand_child is not None and _valid_node(self.grand_child):
            self.grand_child_position = _world_position(self.grand_child)
        self.previous_child_position = self.child_position.copy()
        self.up_vector = _world_axis(self.parent, 1)
        self.stable_x_axis = _world_axis(self.parent, 0)
        self.stable_up_axis = _world_axis(self.parent, 1)

    def _collision_recovery_alpha(self):
        """Return a sub-frame independent easing amount toward the normal path."""
        frame_alpha = self.settings.collision_recovery_stiffness
        # Convert the per-frame stiffness into a per-substep amount so Sub-Frame
        # changes do not make recovery noticeably faster or slower.
        return 1.0 - math.pow(1.0 - frame_alpha, 1.0 / float(self.settings.sub_div))

    def begin_collision_recovery(self, parent_pos, corrected_child_position):
        self.collision_recovery_active = True
        self.collision_recovery_position = corrected_child_position.copy()
        self.collision_recovery_parent_position = parent_pos.copy()

    def recovery_target(self, parent_pos, natural_child_position):
        """Ease the last collision position toward the unconstrained trajectory."""
        if not self.collision_recovery_active:
            return natural_child_position.copy(), False

        # Follow parent translation between samples before easing.  This prevents
        # the stored world-space target from being left behind when the rig moves.
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

        # Stop carrying recovery state once it has essentially converged.
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
        """風向きへ滑らかに骨軸を寄せ、先端ほど遅れて大きくなびかせる。

        013 は「現在の骨軸に対する風の垂直成分」を毎サンプル正規化していた。
        骨が風向きとほぼ平行になると垂直成分がゼロ付近を跨ぎ、特に先端骨で
        曲げ方向が一瞬で反転することがあった。014 は垂直ベクトルを使わず、
        骨軸そのものを風向きへ正規化補間する。したがって風向きを通り越さず、
        強風時でも曲げ方向が裏返らない。
        """
        wind = self.settings.wind
        if wind is None or not _valid_node(wind):
            return Vec3()

        max_force = float(_user_float(wind, "MaxForce", 100.0))
        min_force = float(_user_float(wind, "MinForce", 0.5))
        frequency = max(0.0, float(_user_float(wind, "Frequency", 1.0)))
        tip_multiplier = clamp(float(_user_float(wind, "TipMultiplier", 2.5)), 1.0, 10.0)
        wind_direction = _world_axis(wind, 2).normalized()
        if wind_direction.is_zero():
            return Vec3()

        # 1.0で約30フレーム1周期。下位骨ほど位相を遅らせ、
        # 根元から毛先へ伝わる滑らかな進行波にする。
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

        # 負の風力はコーンと反対方向へ押す。ゼロを跨ぐ場合も、
        # 係数が0へ滑らかに収束してから向きが変わるため不連続にならない。
        target_direction = wind_direction if force >= 0.0 else -wind_direction

        # 根元より先端を強くする。1.0なら均一。
        depth = float(self.chain_index + 1) / float(self.chain_count)
        depth_gain = 1.0 + (tip_multiplier - 1.0) * math.pow(depth, 1.35)

        # 風力を0～0.94の「風向きへの寄り具合」に変換する。
        # tan(84deg) のような発散量を使わないため、500以上の強風でも
        # 先端だけが突然90度を跨ぐことがない。100と500の差は十分残す。
        bend = 1.0 - math.exp(-abs(force) * 0.004 * depth_gain)
        bend = clamp(bend, 0.0, 0.94)

        # normalized lerp。風向きを通り越さないので、骨軸と風向きが
        # 平行になっても曲げ方向の符号反転が発生しない。
        desired_axis = (bone_axis * (1.0 - bend) + target_direction * bend).normalized()
        if desired_axis.is_zero():
            return Vec3()

        desired_child = parent_pos + desired_axis * max(self.bone_length, EPS)

        # aim_by_ratio() 側でスプリング比率を掛けるため、ここでは
        # サブフレーム数で割らない。
        return desired_child - natural_child_position

    def apply_gravity(self):
        gravity = self.settings.gravity
        if gravity is None or not _valid_node(gravity):
            return Vec3()
        strength = float(_user_float(gravity, "Strength", 1.0))
        direction = _world_axis(gravity, 2)
        # Keep the apparent force stable when Sub-Frame is increased.
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

        # Always retain a small absolute restoring force toward the calculation
        # start/saved angle.  This is intentionally independent of collision
        # history so repeated hits can never accumulate roll forever.
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
        self.child.pos = _point(parent_pos + x_axis * length)


def _user_float(node, key, default):
    try:
        value = rt.getUserPropVal(node, key)
        if value is None or str(value) == "undefined":
            return default
        return float(value)
    except Exception:
        return default


def _sphere_data(node):
    center = _world_position(node)
    scale = _matrix_scale(node.transform)
    try:
        base_radius = abs(float(node.radius))
    except Exception:
        base_radius = 10.0
    # A Sphere can be non-uniformly scaled in Max.  Treat it as a conservative
    # sphere using the largest axis so the visible helper is never looser than
    # the collision volume.
    radius = base_radius * max(scale.x, scale.y, scale.z)
    return center, max(EPS, radius)


def _box_data(node):
    # A standard 3ds Max Box pivot is at the center of its bottom face, not at
    # the volume center.  Offset by half the world-space height so the collision
    # volume matches the visible primitive.
    pivot = _world_position(node)
    x_axis = _world_axis(node, 0)
    y_axis = _world_axis(node, 1)
    z_axis = _world_axis(node, 2)
    scale = _matrix_scale(node.transform)
    try:
        width = abs(float(node.width) * scale.x)
    except Exception:
        width = 20.0
    try:
        length = abs(float(node.length) * scale.y)
    except Exception:
        length = 20.0
    try:
        height = abs(float(node.height) * scale.z)
    except Exception:
        height = 20.0
    center = pivot + z_axis * (height * 0.5)
    return center, (x_axis, y_axis, z_axis), Vec3(width * 0.5, length * 0.5, height * 0.5)


def _keep_bone_length(parent_pos, candidate, bone_length, fallback_direction):
    direction = candidate - parent_pos
    if direction.is_zero():
        direction = fallback_direction
    if direction.is_zero():
        direction = Vec3(1.0, 0.0, 0.0)
    return parent_pos + direction.normalized() * bone_length




def _tangent_direction(normal, bone_direction):
    """Return a direction that actually rotates a fixed-length bone away."""
    bone = bone_direction.normalized()
    n = normal.normalized()
    tangent = n - bone * n.dot(bone)
    if not tangent.is_zero():
        return tangent.normalized()
    # Radial/axial pushes can disappear when bone length is restored.
    reference = Vec3(0.0, 0.0, 1.0)
    if abs(bone.dot(reference)) > 0.9:
        reference = Vec3(0.0, 1.0, 0.0)
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


def _push_point_out_box(point, center, axes, half, skin=0.0):
    """Move an inside point to the nearest OBB face and return (point, normal)."""
    p = _obb_local(point, center, axes)
    distances = [
        (half.x - p.x, Vec3(1.0, 0.0, 0.0), 0),
        (half.x + p.x, Vec3(-1.0, 0.0, 0.0), 0),
        (half.y - p.y, Vec3(0.0, 1.0, 0.0), 1),
        (half.y + p.y, Vec3(0.0, -1.0, 0.0), 1),
        (half.z - p.z, Vec3(0.0, 0.0, 1.0), 2),
        (half.z + p.z, Vec3(0.0, 0.0, -1.0), 2),
    ]
    _, normal_local, axis_index = min(distances, key=lambda item: item[0])
    if axis_index == 0:
        p.x = (half.x + skin) * (1.0 if normal_local.x > 0.0 else -1.0)
    elif axis_index == 1:
        p.y = (half.y + skin) * (1.0 if normal_local.y > 0.0 else -1.0)
    else:
        p.z = (half.z + skin) * (1.0 if normal_local.z > 0.0 else -1.0)
    normal_world = (
        axes[0] * normal_local.x + axes[1] * normal_local.y + axes[2] * normal_local.z
    ).normalized()
    return _obb_world(p, center, axes), normal_world


def _segment_box_interval(start, end, center, axes, half):
    """Return (hit, enter_t, exit_t) for a segment against an oriented box."""
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

    # Child joint itself must remain outside.  Push along the tangent of the
    # fixed-length bone sphere so the correction survives length restoration.
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

    # If the root is already inside the helper, the complete bone segment cannot
    # be outside geometrically.  The anchored root is allowed, but the endpoint
    # is still forced toward the outside.
    if _point_inside_sphere(parent_pos, center, target):
        return changed, result

    closest, bone_t = _closest_point_on_segment(center, parent_pos, result)
    delta = closest - center
    dist = delta.length()
    if dist < target:
        normal = delta.normalized()
        if normal.is_zero():
            # Perfect center-line pass: use the center->parent vector only as a
            # reference; tangent conversion below produces a lateral rotation.
            normal = (parent_pos - center).normalized()
        tangent = _tangent_direction(normal, bone_dir)
        penetration = target - dist
        lever = max(0.12, bone_t)
        pushed = result + tangent * (max(penetration, skin) / lever)
        result = _keep_bone_length(parent_pos, pushed, bone_length, fallback)
        changed = True
    return changed, result

def _box_escape_direction(point, center, axes, half, bone_direction):
    """Choose the cheapest box face that can rotate the bone away from the box."""
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
        # A face normal parallel to the bone does not change its direction after
        # the endpoint is normalized back to fixed length, so strongly penalize it.
        score = max(0.0, face_distance) / max(0.02, tangent_len)
        if best is None or score < best[0]:
            best = (score, max(0.0, face_distance), normal, tangent)
    _, penetration, normal, tangent = best
    if tangent.is_zero():
        tangent = _tangent_direction(normal, bone)
    else:
        tangent = tangent.normalized()
    return tangent, penetration


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
        # Probe the middle of the exact inside interval, so even a very thin or
        # rotated BOX cannot be skipped by coarse sampling.
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

def _strict_resolve_child_position(parent_pos, child_pos, spheres, boxes, margin, max_iterations=20):
    """Keep the child joint and, where possible, the complete bone axis outside helpers."""
    if not spheres and not boxes:
        return False, child_pos
    bone_length = distance(parent_pos, child_pos)
    if bone_length < EPS:
        return False, child_pos

    result = child_pos.copy()
    fallback = (child_pos - parent_pos).normalized()
    margin = max(0.0, float(margin))
    skin = max(1.0e-4, margin * 0.01)
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
    # Re-read the actual Max transform after each correction.  This closes the
    # small gap between ideal vector math and real bone controller/pivot behavior.
    for _ in range(5):
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
    """Convert per-frame chain-follow strength to a stable per-iteration amount."""
    strength = clamp(settings.collision_chain_follow, 0.0, 1.0)
    if strength <= EPS:
        return 0.0
    steps = max(1.0, float(settings.sub_div) * float(max(1, iterations)))
    return 1.0 - math.pow(1.0 - strength, 1.0 / steps)


def _bend_follow_weight(upper_direction, lower_direction):
    """Return 0 for a nearly straight joint and 1 for a roughly 90+ degree kink."""
    upper = upper_direction.normalized()
    lower = lower_direction.normalized()
    if upper.is_zero() or lower.is_zero():
        return 0.0
    dot = clamp(upper.dot(lower), -1.0, 1.0)
    # Do not disturb ordinary small bends.  Follow ramps up after ~25 degrees
    # and reaches full strength at 90 degrees.  This makes the feature act as a
    # collision kink suppressor rather than a general chain straightener.
    straight_dot = math.cos(math.radians(25.0))
    if dot >= straight_dot:
        return 0.0
    return clamp((straight_dot - dot) / straight_dot, 0.0, 1.0)


def _apply_collision_chain_follow(chain_data_paths, spheres, boxes):
    """Share a lower-bone collision bend with its upstream bones.

    The 006/007 solver guarantees clearance by rotating the bone whose segment
    intersects a helper.  If that intersection is extremely close to a joint,
    the required endpoint correction can become a large one-joint bend.  008
    performs a short chain relaxation pass: a corrected lower bone pulls its
    parent bone toward the lower bone's direction.  The influence propagates
    upward, then the strict collision pass is run again so the softer pose does
    not re-enter a Sphere/BOX.
    """
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
        # Bottom-up pull.  A real collision on a lower segment can propagate
        # through several ancestors in the same pass, with the bend angle itself
        # controlling how much correction is actually applied at each joint.
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

        # Pulling an ancestor also moves all descendants.  Re-run the hard
        # clearance pass root-to-tip after every relaxation iteration so the
        # visual smoothing never trades away the no-penetration behavior.
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
    """Apply collision and smoothly recover toward the unconstrained trajectory."""
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
        max_iterations=12,
    )

    if hit:
        # Refresh the recovery anchor on every contact.  Once contact ends, this
        # corrected target is eased back toward the natural Spring path instead
        # of being discarded in a single sample.
        data.begin_collision_recovery(parent_pos, target)
        corrected = target.copy()
        return True, True, target, corrected

    if recovering:
        # While easing out, use the recovery target on both sides of Spring
        # blending.  This is what removes the one-frame snap from 006.
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
    selected = [node for node in rt.selection]
    if not selected:
        raise ValueError("スプリング計算する親子ノードを選択してください。")
    if settings.end_frame <= settings.start_frame:
        raise ValueError("終了フレームは開始フレームより後にしてください。")

    paths = _selected_chain_paths(selected, settings.include_root, settings.include_branch_points)
    selected_original = list(selected)
    spring_data = OrderedDict()
    chain_data_paths = []
    proxies = []
    previous_coords = _enter_world_coords()

    wind_nodes = _scene_nodes_by_type(WIND_TAG) if settings.use_wind else []
    settings.wind = wind_nodes[0] if wind_nodes else None
    gravity_nodes = _scene_nodes_by_type(GRAVITY_TAG) if settings.use_gravity else []
    settings.gravity = gravity_nodes[0] if gravity_nodes else None
    spheres = _scene_nodes_by_type(SPHERE_TAG) if settings.is_collision else []
    boxes = _scene_nodes_by_type(BOX_TAG) if settings.is_collision else []

    try:
        with pymxs.attime(settings.start_frame):
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

        # 012 rest pose rule: every SpringData has already captured one local
        # reference angle at the calculation start (or loaded the explicitly
        # saved angle).  This reference remains authoritative for the whole run.

        # Pose Match: preserve the original child world motion before deleting target keys.
        if settings.is_pose_match:
            sample_count = settings.end_frame - settings.start_frame + 1
            for offset, frame in enumerate(range(settings.start_frame, settings.end_frame + 1)):
                with pymxs.animate(True):
                    with pymxs.attime(frame):
                        for data in spring_data.values():
                            data.sample_proxy(frame)
                _progress(progression_callback, (offset + 1) * 15.0 / float(max(1, sample_count)), "ポーズ合わせをサンプル中")

        # Remove keys only in the calculation range, matching the original tool's behavior.
        for data in spring_data.values():
            _delete_rotation_keys(data.parent, settings.start_frame, settings.end_frame)
            if abs(spring.extend) > EPS:
                _delete_position_keys(data.child, settings.start_frame, settings.end_frame)

        # Re-create the start-frame keys from the pose captured before key deletion.
        with pymxs.animate(True):
            with pymxs.attime(settings.start_frame):
                for data in spring_data.values():
                    _set_world_rotation_from_matrix(data.parent, data.start_parent_transform)
                    if abs(spring.extend) > EPS:
                        data.child.pos = data.start_child_transform.row4

        # Build simulation frame list.
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
        with pymxs.animate(True):
            for frame_index, frame in enumerate(frames):
                with pymxs.attime(frame):
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
                        # Final hard correction uses the actual Max bone pose, not only
                        # the simulated child target.  Sphere/BOX collision is therefore
                        # considerably less permissive than the 005 capsule implementation.
                        if _strict_resolve_pose(data, spheres, boxes, up_vector):
                            has_collision = True
                            collision_active = True
                            corrected = _world_position(data.child)
                            data.begin_collision_recovery(_world_position(data.parent), corrected)
                        data.extend_bone(corrected)
                        # ``has_collision`` means real contact this sample;
                        # ``collision_active`` also includes the soft recovery
                        # period.  Keep them separate so chain-follow stops as
                        # soon as the obstacle is cleared.
                        data.contact_active = bool(has_collision)
                        data.update(collision_active, corrected)
                        if grand_parent_data is not None:
                            grand_parent_data.has_child_collide = collision_active

                    # 008: collision response is no longer isolated to a single
                    # segment.  A sharp lower-bone correction softly pulls its
                    # upstream joints, then hard clearance is verified again.
                    if settings.is_collision and settings.collision_chain_follow > EPS:
                        if _apply_collision_chain_follow(chain_data_paths, spheres, boxes):
                            for data in spring_data.values():
                                data.sync_final_pose()

                progress = start_progress + (frame_index + 1) * (100.0 - start_progress) / float(total)
                _progress(progression_callback, progress, "スプリング計算中")
                if frame_index % 5 == 0:
                    try:
                        rt.redrawViews()
                    except Exception:
                        pass

        if settings.wipe_subframe and settings.sub_div > 1:
            for data in spring_data.values():
                try:
                    _delete_non_integer_keys(_rotation_controller(data.parent), settings.start_frame, settings.end_frame)
                except Exception:
                    pass
                if abs(spring.extend) > EPS:
                    try:
                        _delete_non_integer_keys(_position_controller(data.child), settings.start_frame, settings.end_frame)
                    except Exception:
                        pass

        # 012: smooth standard XYZ Euler keys after the solve.  The world-space
        # pose is unchanged; only equivalent Euler representations are unwrapped
        # so an isolated +/-180/360 branch cannot appear as a one-frame twitch.
        for data in spring_data.values():
            _smooth_euler_rotation_keys(data.parent, settings.start_frame, settings.end_frame)

        _progress(progression_callback, 100.0, "完了")
    finally:
        for proxy in proxies:
            if _valid_node(proxy):
                try:
                    rt.delete(proxy)
                except Exception:
                    pass
        try:
            _select_nodes(selected_original)
            rt.redrawViews()
        except Exception:
            pass
        _restore_coords(previous_coords)


def _helper_transform_from_node(node):
    if node is None:
        return rt.matrix3(1)
    center = _world_position(node)
    x_axis = _world_axis(node, 0)
    y_axis = _world_axis(node, 1)
    z_axis = _world_axis(node, 2)
    return rt.matrix3(_point(x_axis), _point(y_axis), _point(z_axis), _point(center))


def create_collision_sphere():
    selected = [node for node in rt.selection]
    targets = selected if selected else [None]
    created = []
    for node in targets:
        radius = 10.0
        if node is not None:
            children = _children(node)
            if children:
                radius = max(1.0, distance(_world_position(node), _world_position(children[0])) * 0.75)
        sphere = rt.Sphere(radius=radius, segs=16)
        base_name = "SpringCollisionSphere" if node is None else "{0}_collision_sphere".format(node.name)
        sphere.name = _unique_scene_name(base_name)
        if node is not None:
            sphere.pos = _point(_world_position(node))
        _set_type(sphere, SPHERE_TAG)
        created.append(sphere)
    if created:
        _select_nodes(created)
    rt.redrawViews()
    return created


def create_collision_box():
    selected = [node for node in rt.selection]
    targets = selected if selected else [None]
    created = []
    for node in targets:
        size = 20.0
        if node is not None:
            children = _children(node)
            if children:
                size = max(2.0, distance(_world_position(node), _world_position(children[0])) * 1.5)
        box = rt.Box(length=size, width=size, height=size, lengthsegs=1, widthsegs=1, heightsegs=1)
        base_name = "SpringCollisionBox" if node is None else "{0}_collision_box".format(node.name)
        box.name = _unique_scene_name(base_name)
        if node is not None:
            # Place the visible volume center on the selected node.  Box.pos is
            # the bottom-face center, so shift the pivot by half the new height.
            center = _world_position(node)
            x_axis = _world_axis(node, 0)
            y_axis = _world_axis(node, 1)
            z_axis = _world_axis(node, 2)
            pivot = center - z_axis * (size * 0.5)
            box.transform = rt.matrix3(_point(x_axis), _point(y_axis), _point(z_axis), _point(pivot))
        _set_type(box, BOX_TAG)
        created.append(box)
    if created:
        _select_nodes(created)
    rt.redrawViews()
    return created


def remove_collision_helpers():
    nodes = []
    for tag in (SPHERE_TAG, BOX_TAG, LEGACY_CAPSULE_TAG, LEGACY_PLANE_TAG):
        nodes.extend(_scene_nodes_by_type(tag))
    unique = []
    seen = set()
    for node in nodes:
        handle = _node_handle(node)
        if handle not in seen:
            seen.add(handle)
            unique.append(node)
    for node in unique:
        if _valid_node(node):
            rt.delete(node)
    rt.redrawViews()
    return len(unique)

def create_wind():
    wind = rt.Cone(radius1=5.0, radius2=0.0, height=15.0)
    wind.name = _unique_scene_name("spring_wind")
    _set_type(wind, WIND_TAG)
    rt.setUserPropVal(wind, "MaxForce", 100.0)
    rt.setUserPropVal(wind, "MinForce", 0.5)
    rt.setUserPropVal(wind, "Frequency", 1.0)
    rt.setUserPropVal(wind, "TipMultiplier", 2.5)
    rt.select(wind)
    rt.redrawViews()
    return wind


def _write_wind_values(wind_nodes, max_force, min_force, frequency, tip_multiplier):
    for wind in wind_nodes:
        rt.setUserPropVal(wind, "MaxForce", float(max_force))
        rt.setUserPropVal(wind, "MinForce", float(min_force))
        rt.setUserPropVal(wind, "Frequency", float(frequency))
        rt.setUserPropVal(wind, "TipMultiplier", float(tip_multiplier))
    return wind_nodes


def set_wind_values(max_force, min_force, frequency, tip_multiplier=2.5):
    # この関数は作成/更新ボタン専用。風が無い場合だけ明示的に作成する。
    wind_nodes = [node for node in rt.selection if _get_type(node) == WIND_TAG]
    if not wind_nodes:
        wind_nodes = _scene_nodes_by_type(WIND_TAG)
    if not wind_nodes:
        wind_nodes = [create_wind()]
    return _write_wind_values(wind_nodes, max_force, min_force, frequency, tip_multiplier)


def sync_existing_wind_values(max_force, min_force, frequency, tip_multiplier=2.5):
    # 適用時はUI値を同期するだけ。勝手にオブジェクトは作らない。
    wind_nodes = _scene_nodes_by_type(WIND_TAG)
    if not wind_nodes:
        raise ValueError("風が有効ですが、風オブジェクトがありません。先に［風オブジェクト作成 / 値更新］を押してください。")
    return _write_wind_values(wind_nodes, max_force, min_force, frequency, tip_multiplier)


def create_gravity():
    gravity = rt.Cone(radius1=5.0, radius2=0.0, height=15.0)
    gravity.name = _unique_scene_name("spring_gravity")
    _set_type(gravity, GRAVITY_TAG)
    rt.setUserPropVal(gravity, "Strength", 1.0)
    rt.select(gravity)
    rt.redrawViews()
    return gravity


def set_gravity_value(strength):
    gravity_nodes = [node for node in rt.selection if _get_type(node) == GRAVITY_TAG]
    if not gravity_nodes:
        gravity_nodes = _scene_nodes_by_type(GRAVITY_TAG)
    if not gravity_nodes:
        gravity_nodes = [create_gravity()]
    for gravity in gravity_nodes:
        rt.setUserPropVal(gravity, "Strength", float(strength))
    return gravity_nodes


def sync_existing_gravity_value(strength):
    # 風と同様、適用時はUI値を同期するだけで新規作成しない。
    gravity_nodes = _scene_nodes_by_type(GRAVITY_TAG)
    if not gravity_nodes:
        raise ValueError("重力が有効ですが、重力オブジェクトがありません。先に［重力オブジェクト作成 / 値更新］を押してください。")
    for gravity in gravity_nodes:
        rt.setUserPropVal(gravity, "Strength", float(strength))
    return gravity_nodes


_POSE_COPY = {}


def copy_pose():
    global _POSE_COPY
    _POSE_COPY = {}
    for node in rt.selection:
        _POSE_COPY[_node_handle(node)] = _copy_matrix(node.transform)
    return len(_POSE_COPY)


def paste_pose():
    count = 0
    for node in rt.selection:
        tm = _POSE_COPY.get(_node_handle(node))
        if tm is not None:
            node.transform = _copy_matrix(tm)
            count += 1
    rt.redrawViews()
    return count


def straighten_selected():
    previous_coords = _enter_world_coords()
    try:
        count = 0
        for node in rt.selection:
            children = _children(node)
            if not children:
                continue
            target = _world_position(children[0])
            up = _world_axis(node, 1)
            if _aim_x_axis(node, target, up):
                count += 1
        rt.redrawViews()
        return count
    finally:
        _restore_coords(previous_coords)


# UIから同一ファイル内のコア関数を参照するための別名。
core = sys.modules[__name__]

_WINDOW = None


def _max_main_window():
    if GetQMaxMainWindow is not None:
        try:
            return GetQMaxMainWindow()
        except Exception:
            pass
    try:
        return QtWidgets.QWidget.find(rt.windows.getMAXHWND())
    except Exception:
        return None


class CollapsibleSection(QtWidgets.QFrame):
    """矢印付き見出しで内容を開閉できるUIセクション。"""

    def __init__(self, title, parent=None, expanded=True):
        super(CollapsibleSection, self).__init__(parent)
        # 022: 3ds MaxのダークテーマではStyledPanelの標準枠が描画上ほぼ
        # 見えないため、テーマ任せにせず明示的な枠色を指定する。
        self.setObjectName("SpringMaxCollapsibleSection")
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "QFrame#SpringMaxCollapsibleSection {"
            " border: 1px solid #777777;"
            " border-radius: 3px;"
            " background-color: transparent;"
            "}"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(2)

        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.setObjectName("SpringMaxSectionToggle")
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(bool(expanded))
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )
        self.toggle_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.toggle_button.setStyleSheet(
            "QToolButton#SpringMaxSectionToggle {"
            " border: none;"
            " border-radius: 2px;"
            " background-color: rgba(255, 255, 255, 14);"
            " font-weight: bold;"
            " text-align: left;"
            " padding: 4px 2px;"
            "}"
            "QToolButton#SpringMaxSectionToggle:hover {"
            " background-color: rgba(255, 255, 255, 28);"
            "}"
        )
        self.toggle_button.toggled.connect(self._set_expanded)

        self.content = QtWidgets.QFrame()
        self.content.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.content.setVisible(bool(expanded))
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content)

    def _set_expanded(self, expanded):
        self.toggle_button.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )
        self.content.setVisible(bool(expanded))
        self.updateGeometry()


class SpringMaxDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SpringMaxDialog, self).__init__(parent or _max_main_window())
        self.setObjectName("SpringMaxDialog")
        self.setWindowTitle("SpringMax {0}".format(BUILD))
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.Tool)
        # 019: Full HDの作業領域内へ収まる初期サイズにする。
        # 設定群はスクロール領域へ入れるため、この高さより小さくリサイズしても
        # レイアウトのminimumSizeHintに押し戻されない。
        self.setMinimumSize(390, 560)
        self._cancel_requested = False
        self._build_ui()
        self.resize(430, 830)
        self._load_range()

    def _spin(self, value, minimum=0.0, maximum=1.0, step=0.05, decimals=3):
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setDecimals(decimals)
        widget.setValue(value)
        return widget

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # 019: 高さを必要とする設定群だけをスクロール可能にし、進捗表示と
        # 実行ボタンはウィンドウ下部へ常時表示する。
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll_content = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(scroll_content)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(8)

        note = QtWidgets.QLabel("親→子の連続したノードを選択して実行します。ローカルX軸が子方向を向くリグを想定しています。")
        note.setWordWrap(True)
        root.addWidget(note)

        build_label = QtWidgets.QLabel("ビルド: {0}  /  3ds Max 2025以降  /  PySide6".format(BUILD))
        root.addWidget(build_label)

        spring_group = CollapsibleSection("スプリング")
        form = QtWidgets.QFormLayout(spring_group.content)
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

        range_group = CollapsibleSection("キー設定")
        range_layout = QtWidgets.QGridLayout(range_group.content)
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

        col_group = CollapsibleSection("当たり判定", expanded=False)
        col_layout = QtWidgets.QGridLayout(col_group.content)
        self.collision_check = QtWidgets.QCheckBox("衝突判定を有効化")
        self.collision_margin = self._spin(0.0, 0.0, 1000.0, 0.1, 3)
        self.collision_margin.setToolTip("衝突物をこの値だけ外側へ膨らませて判定します。めり込みが気になる場合に少し増やしてください。")
        self.collision_recovery_stiffness = self._spin(0.15, 0.01, 1.0, 0.05, 3)
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

        wind_group = CollapsibleSection("風", expanded=False)
        wind_layout = QtWidgets.QFormLayout(wind_group.content)
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
        root.addWidget(wind_group)

        gravity_group = CollapsibleSection("重力", expanded=False)
        gravity_layout = QtWidgets.QFormLayout(gravity_group.content)
        self.gravity_enable = QtWidgets.QCheckBox("重力を有効化")
        self.gravity_enable.setChecked(False)
        self.gravity_enable.setToolTip("オフなら、シーンに重力オブジェクトが残っていても計算には使用しません。")
        self.gravity_strength = self._spin(1.0, -1000.0, 1000.0, 0.1)
        gravity_button = QtWidgets.QPushButton("重力オブジェクト作成 / 値更新")
        gravity_button.clicked.connect(self._set_gravity)
        gravity_layout.addRow(self.gravity_enable)
        gravity_layout.addRow("重力の強さ", self.gravity_strength)
        gravity_layout.addRow(gravity_button)
        gravity_note = QtWidgets.QLabel("円錐の先端方向（ローカルZ+）が重力方向です。")
        gravity_note.setWordWrap(True)
        gravity_layout.addRow(gravity_note)
        root.addWidget(gravity_group)

        angle_group = CollapsibleSection("基準角度", expanded=False)
        angle_layout = QtWidgets.QHBoxLayout(angle_group.content)
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

        pose_group = CollapsibleSection("骨ポーズ", expanded=False)
        pose_layout = QtWidgets.QHBoxLayout(pose_group.content)
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

        root.addStretch(1)
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, 1)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QtWidgets.QLabel("待機中")
        self.status.setWordWrap(True)
        outer.addWidget(self.progress)
        outer.addWidget(self.status)

        buttons = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("適用")
        self.apply_button.setMinimumHeight(34)
        self.cancel_button = QtWidgets.QPushButton("キャンセル")
        self.cancel_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.cancel_button.clicked.connect(self._request_cancel)
        buttons.addWidget(self.apply_button, 1)
        buttons.addWidget(self.cancel_button)
        outer.addLayout(buttons)

        # QDialog treats Enter in a spin box as activation of an auto-default
        # button.  In older builds this could accidentally press "球作成" while
        # the user was only confirming a numeric value.  Creation/execution is
        # now possible only by explicitly clicking the corresponding button.
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    def _load_range(self):
        try:
            self.start_frame.setValue(int(round(float(rt.animationRange.start.frame))))
            self.end_frame.setValue(int(round(float(rt.animationRange.end.frame))))
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
                int(round(float(rt.animationRange.start.frame))),
                int(round(float(rt.animationRange.end.frame))),
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
            self.status.setText("エラー: {0}".format(exc))
            traceback.print_exc()

    def _add_sphere(self):
        self._run_small_action(core.create_collision_sphere, lambda result: "球を{0}個作成しました。".format(len(result)))

    def _add_box(self):
        self._run_small_action(core.create_collision_box, lambda result: "ボックスを{0}個作成しました。".format(len(result)))

    def _clear_collision(self):
        self._run_small_action(core.remove_collision_helpers, lambda count: "衝突物を{0}個削除しました。".format(count))

    def _set_wind(self):
        def action():
            return core.set_wind_values(
                self.wind_max.value(), self.wind_min.value(),
                self.wind_freq.value(), self.wind_tip.value(),
            )
        self._run_small_action(action, "風を設定しました。コーンのローカルZ方向が風向きです。")
        self.wind_enable.setChecked(True)

    def _set_gravity(self):
        def action():
            return core.set_gravity_value(self.gravity_strength.value())
        self._run_small_action(action, "重力を設定しました。円錐の先端方向が重力方向です。")
        self.gravity_enable.setChecked(True)

    def _save_angles(self):
        self._run_small_action(
            core.save_reference_angles,
            lambda count: "{0}ノードの角度を基準角度として保存しました。".format(count),
        )

    def _restore_angles(self):
        self._run_small_action(
            core.restore_reference_angles,
            lambda count: "{0}ノードを保存角度へ戻しました。".format(count),
        )

    def _clear_angles(self):
        self._run_small_action(
            core.clear_reference_angles,
            lambda count: "{0}ノードの保存角度を解除しました。".format(count),
        )

    def _copy_pose(self):
        self._run_small_action(core.copy_pose, lambda count: "{0}ノードの姿勢をコピーしました。".format(count))

    def _paste_pose(self):
        self._run_small_action(core.paste_pose, lambda count: "{0}ノードへ姿勢を貼り付けました。".format(count))

    def _straighten(self):
        self._run_small_action(core.straighten_selected, lambda count: "{0}ノードを子方向へ整列しました。".format(count))

    def _apply(self):
        start_frame, end_frame = self._effective_range()

        # 014: 入力欄の値を［適用］時にも既存ヘルパーへ同期する。
        # 012までは更新ボタンを押さないと100→500に変えても計算値が変わらなかった。
        # ただし、ここでは風/重力オブジェクトを勝手に作成しない。
        try:
            if self.wind_enable.isChecked():
                core.sync_existing_wind_values(
                    self.wind_max.value(), self.wind_min.value(),
                    self.wind_freq.value(), self.wind_tip.value(),
                )
            if self.gravity_enable.isChecked():
                core.sync_existing_gravity_value(self.gravity_strength.value())
        except Exception as exc:
            self.status.setText("エラー: {0}".format(exc))
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

        try:
            # Keep the entire simulation in a single 3ds Max undo record.
            # If the result is not what was expected, one Ctrl+Z restores the
            # state from immediately before Apply was pressed.
            with pymxs.undo(True):
                core.start_compute(spring, settings, self._progress_callback)
            self.status.setText("完了しました。問題があればCtrl+Zで1回で戻せます。")
        except core.CancelledError:
            self.status.setText("キャンセルしました。必要ならCtrl+Zで計算前へ戻してください。")
        except Exception as exc:
            self.status.setText("エラー: {0}".format(exc))
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(self, "SpringMax", str(exc))
        finally:
            self.apply_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress.setValue(0)


def show():
    global _WINDOW

    # Close SpringMax / legacy Spring Magic windows left alive by older builds.  Each build uses a
    # unique Python package name so module caching cannot make an old core run.
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            for widget in app.topLevelWidgets():
                if widget.objectName() in ("SpringMaxDialog", "SpringMagicMaxDialog"):
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
    _WINDOW = SpringMaxDialog()
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW


# Run Script で実行したらそのままUIを開く。
show()
