import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_line_plane
import numpy as np
import os
from bpy_extras import view3d_utils
from .functions_general import *
from .functions_drawing import *
from .functions_modal_keymap import *
from .classes import *
from .keymap import addon_keymaps


def match_loops_vecs(self, loop, o_tangs, flip_axis=None):
    tang = self._object_bm.verts[loop.point.index].link_loops[loop.index].calc_tangent(
    )

    small = 0
    small_ind = None
    for o, o_tang in enumerate(o_tangs):
        t_tang = o_tang.copy()
        if flip_axis != None:
            t_tang[flip_axis] *= -1

        ang = tang.angle(t_tang)
        if ang < small or small_ind == None:
            small_ind = o
            small = ang

    return small_ind


#
#


def set_new_normals(self):
    self._object.data.edges.foreach_set(
        'use_edge_sharp', self._container.og_sharp)

    # Lerp between cached and new normals by the filter weights
    self._container.new_norms = self._container.cache_norms * \
        (1.0-self._container.filter_weights) + \
        self._container.new_norms * self._container.filter_weights

    # Get the scale factor to normalized new normals
    scale = 1 / np.sqrt(np.sum(np.square(self._container.new_norms), axis=1))
    self._container.new_norms = self._container.new_norms*scale[:, None]

    # self._container.new_norms.shape = [len(self._object.data.loops), 3]
    self._object.data.normals_split_custom_set(self._container.new_norms)

    return


def loop_norm_set(self, loop, og_vec, to_vec):
    # weight = None
    # if self._container.filter_weights != None:
    #     weight = self._container.filter_weights[loop.point.index]

    # if weight == None:
    #     new_vec = to_vec
    # else:
    #     new_vec = og_vec.lerp(to_vec, weight)

    # loop.normal = new_vec

    # axis = []
    # if self._mirror_x:
    #     axis.append(0)
    # if self._mirror_y:
    #     axis.append(1)
    # if self._mirror_z:
    #     axis.append(2)

    # for ind in axis:
    #     if ind == 0:
    #         mir_loop = loop.x_mirror
    #     if ind == 1:
    #         mir_loop = loop.y_mirror
    #     if ind == 2:
    #         mir_loop = loop.z_mirror

    #     if mir_loop != None:
    #         mir_norm = loop.normal.copy()
    #         mir_norm[ind] *= -1

    #         mir_loop.normal = mir_norm
    return


def mirror_normals(self, sel_inds, axis):

    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]

            if axis == 0:
                mir_loop = loop.x_mirror
            if axis == 1:
                mir_loop = loop.y_mirror
            if axis == 2:
                mir_loop = loop.z_mirror

            if mir_loop != None:
                mir_norm = loop.normal.copy()
                mir_norm[axis] *= -1

                mir_loop.normal = mir_norm

                self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def incremental_rotate_vectors(self, sel_inds, axis, increment):
    sel_cos = self._container.get_selected_loop_cos()
    avg_loc = average_vecs(sel_cos)

    self._container.cache_current_normals()

    self._mode_cache.clear()
    self._mode_cache.append(self._mouse_reg_loc)
    self._mode_cache.append(avg_loc)
    self._mode_cache.append(0)

    self.translate_mode = 2
    self.translate_axis = axis
    rotate_vectors(self, sel_inds, math.radians(
        increment * self._rot_increment))
    self.translate_mode = 0
    self.translate_axis = 2
    self._mode_cache.clear()
    return


def rotate_vectors(self, sel_inds, angle):
    if self.translate_axis == 0:
        axis = 'X'
    if self.translate_axis == 1:
        axis = 'Y'
    if self.translate_axis == 2:
        axis = 'Z'

    rot = np.array(Matrix.Rotation(angle, 3, axis))

    # Viewspace rotation matrix
    if self.translate_mode == 0:
        persp_mat = bpy.context.region_data.view_matrix.to_3x3().normalized()
        loc_mat = self._object.matrix_world.to_3x3().normalized()

        self._container.new_norms[self._container.sel_status] = np.array(
            loc_mat).dot(self._container.cache_norms[self._container.sel_status].T).T
        self._container.new_norms[self._container.sel_status] = np.array(
            persp_mat).dot(self._container.new_norms[self._container.sel_status].T).T
        self._container.new_norms[self._container.sel_status] = rot.dot(
            self._container.new_norms[self._container.sel_status].T).T
        self._container.new_norms[self._container.sel_status] = np.array(
            persp_mat.inverted()).dot(self._container.new_norms[self._container.sel_status].T).T
        self._container.new_norms[self._container.sel_status] = np.array(
            loc_mat.inverted()).dot(self._container.new_norms[self._container.sel_status].T).T

    # World space rotation matrix
    elif self.translate_mode == 1:
        loc_mat = self._object.matrix_world.to_3x3().normalized()

        self._container.new_norms[self._container.sel_status] = np.array(
            loc_mat).dot(self._container.cache_norms[self._container.sel_status].T).T
        self._container.new_norms[self._container.sel_status] = rot.dot(
            self._container.new_norms[self._container.sel_status].T).T
        self._container.new_norms[self._container.sel_status] = np.array(
            loc_mat.inverted()).dot(self._container.new_norms[self._container.sel_status].T).T

    # Local space roatation matrix
    elif self.translate_mode == 2:
        if self.gizmo_click:
            orb_mat = self._orbit_ob.matrix_world.to_3x3().normalized()
            loc_mat = self._object.matrix_world.to_3x3().normalized()

            self._container.new_norms[self._container.sel_status] = np.array(
                loc_mat).dot(self._container.cache_norms[self._container.sel_status].T).T
            self._container.new_norms[self._container.sel_status] = np.array(
                orb_mat.inverted()).dot(self._container.new_norms[self._container.sel_status].T).T
            self._container.new_norms[self._container.sel_status] = rot.dot(
                self._container.new_norms[self._container.sel_status].T).T
            self._container.new_norms[self._container.sel_status] = np.array(
                orb_mat).dot(self._container.new_norms[self._container.sel_status].T).T
            self._container.new_norms[self._container.sel_status] = np.array(
                loc_mat.inverted()).dot(self._container.new_norms[self._container.sel_status].T).T

        else:
            self._container.new_norms[self._container.sel_status] = rot.dot(
                self._container.cache_norms[self._container.sel_status].T).T

    set_new_normals(self)
    self.redraw_active = True

    return


#
# AXIS ALIGNMENT
#
def flatten_normals(self, sel_inds, axis):
    update_filter_weights(self)
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]

            vec = loop.normal.copy()
            vec[axis] = 0.0

            if vec.length > 0.0:
                loop_norm_set(self, loop, loop.normal, vec)
        self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def align_to_axis_normals(self, sel_inds, axis, dir):
    update_filter_weights(self)
    vec = Vector((0, 0, 0))

    vec[axis] = 1.0*dir
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]

            loop_norm_set(self, loop, loop.normal, vec.copy())

            self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


#
# MANIPULATE NORMALS
#
def average_vertex_normals(self, sel_inds):
    update_filter_weights(self)

    new_norms = []
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]

            vec = average_vecs(
                [loop.normal for loop in po.loops if loop.select])

            new_norms.append(vec)
        else:
            new_norms.append(None)

    for i, ind in enumerate(sel_inds):
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]
            loop_norm_set(self, loop, loop.normal, new_norms[i])

            self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def average_selected_normals(self, sel_inds):
    update_filter_weights(self)
    avg_vec = Vector((0, 0, 0))
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            vec = average_vecs(
                [loop.normal for loop in po.loops if loop.select])
            avg_vec += vec

            self.redraw = True

    avg_vec = (avg_vec/len(sel_inds)).normalized()

    if avg_vec.length > 0.0:
        for ind in sel_inds:
            po = self._container.points[ind[0]]
            if po.valid:
                loop = po.loops[ind[1]]

                loop_norm_set(self, loop, loop.normal, avg_vec.copy())

        set_new_normals(self)
        add_to_undostack(self, 1)

    return


def smooth_normals(self, sel_inds, fac):
    update_filter_weights(self)

    calc_norms = None
    for i in range(self._smooth_iterations):
        calc_norms = []
        for po in self._container.points:
            if len(po.loops) > 0 and po.valid:
                vec = average_vecs([loop.normal for loop in po.loops])
                calc_norms.append(vec)
            else:
                calc_norms.append(None)

        for ind in sel_inds:
            po = self._container.points[ind[0]]
            if po.valid:
                loop = po.loops[ind[1]]

                l_vs = [ed.other_vert(self._object_bm.verts[po.index])
                        for ed in self._object_bm.verts[po.index].link_edges]

                smooth_vec = Vector((0, 0, 0))
                smooth_vec = average_vecs(
                    [loop.normal.lerp(calc_norms[ov.index], fac) for ov in l_vs])

                if smooth_vec.length > 0:
                    loop_norm_set(self, loop, loop.normal, loop.normal.lerp(
                        smooth_vec, self._smooth_strength))

    self.redraw = True
    set_new_normals(self)
    add_to_undostack(self, 1)
    return


#
# NORMAL DIRECTION
#
def flip_normals(self, sel_inds):
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]
            loop.normal *= -1
            self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def set_outside_inside(self, sel_inds, direction):
    update_filter_weights(self)
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]

            if self._object_smooth:
                poly_norm = Vector((0, 0, 0))
                for bm_loop in self._object_bm.verts[po.index].link_loops:
                    poly_norm += self._object.data.polygons[bm_loop.face.index].normal * direction

                if poly_norm.length > 0.0:
                    loop_norm_set(self, loop, loop.normal,
                                  poly_norm/len(po.loops))

            else:
                loop.normal = self._object_bm.loops[loop.loop_index].face.normal.copy(
                ) * direction

            self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def reset_normals(self, sel_inds):
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            loop = po.loops[ind[1]]
            loop.reset_normal()
        self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def set_normals_from_faces(self, sel_inds):
    update_filter_weights(self)
    for ind in sel_inds:
        po = self._container.points[ind[0]]
        if po.valid:
            sel_faces = [
                loop.face_index for loop in po.loops if loop.select or po.select]

            loop = po.loops[ind[1]]

            poly_norm = Vector((0, 0, 0))
            for f_ind in sel_faces:
                poly_norm += self._object.data.polygons[f_ind].normal

            if poly_norm.length > 0.0:
                loop_norm_set(self, loop, loop.normal,
                              poly_norm/len(sel_faces))

            self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


#
# COPY/PASTE
#
def copy_active_to_selected(self, sel_inds):
    update_filter_weights(self)
    if self._active_point != None:
        norms, tangs = get_po_loop_data(self, self._active_point)

        for ind in sel_inds:
            po = self._container.points[ind[0]]
            if po.valid:
                loop = po.loops[ind[1]]

                m_ind = match_loops_vecs(self, loop, tangs)

                loop_norm_set(
                    self, loop, loop.normal, norms[m_ind].copy())

        self.redraw = True

    set_new_normals(self)
    add_to_undostack(self, 1)
    return


def get_po_loop_data(self, po_loop):
    norms = None
    tangs = None

    if po_loop != None:
        if po_loop.type == 'POINT':
            norms = [loop.normal for loop in po_loop.loops]
            tangs = []

            for o_loop in self._object_bm.verts[po_loop.index].link_loops:
                tangs.append(o_loop.calc_tangent())

        elif po_loop.type == 'LOOP':
            norms = [po_loop.normal]
            tangs = [
                self._object_bm.verts[po_loop.point.index].link_loops[po_loop.index].calc_tangent()]

    return norms, tangs


def paste_normal(self, sel_inds):
    update_filter_weights(self)
    if self._copy_normals != None and self._copy_normals_tangs != None:
        for ind in sel_inds:
            po = self._container.points[ind[0]]
            if po.valid:
                loop = po.loops[ind[1]]

                m_ind = match_loops_vecs(
                    self, loop, self._copy_normals_tangs)

                loop_norm_set(
                    self, loop, loop.normal, self._copy_normals[m_ind].copy())

                self.redraw = True
    set_new_normals(self)
    add_to_undostack(self, 1)
    return


#
#


def translate_axis_draw(self):
    mat = None
    if self.translate_mode == 0:
        self.translate_draw_line.clear()

    elif self.translate_mode == 1:
        mat = generate_matrix(Vector((0, 0, 0)), Vector(
            (0, 0, 1)), Vector((0, 1, 0)), False, True)
        mat.translation = self._mode_cache[1]

    elif self.translate_mode == 2:
        mat = self._object.matrix_world.normalized()
        mat.translation = self._mode_cache[1]

    if mat != None:
        self.translate_draw_line.clear()

        if self.translate_axis == 0:
            vec = Vector((1000, 0, 0))
        if self.translate_axis == 1:
            vec = Vector((0, 1000, 0))
        if self.translate_axis == 2:
            vec = Vector((0, 0, 1000))

        self.translate_draw_line.append(mat @ vec)
        self.translate_draw_line.append(mat @ -vec)

    self.batch_translate_line = batch_for_shader(
        self.shader_3d, 'LINES', {"pos": self.translate_draw_line})
    return


def clear_translate_axis_draw(self):
    self.batch_translate_line = batch_for_shader(
        self.shader_3d, 'LINES', {"pos": []})
    return


def translate_axis_change(self, text, axis):
    if self.translate_axis != axis:
        self.translate_axis = axis
        self.translate_mode = 1

    else:
        self.translate_mode += 1
        if self.translate_mode == 3:
            self.translate_mode = 0
            self.translate_axis = 2

    if self.translate_mode == 0:
        self._window.set_status('VIEW ' + text)
    elif self.translate_mode == 1:
        self._window.set_status('GLOBAL ' + text)
    else:
        self._window.set_status('LOCAL ' + text)

    translate_axis_draw(self)

    self._container.restore_cached_normals()
    self._container.cache_current_normals()
    return


def translate_axis_side(self):
    view_vec = view3d_utils.region_2d_to_vector_3d(
        self.act_reg, self.act_rv3d, Vector(self._mouse_reg_loc))

    if self.translate_mode == 1:
        mat = generate_matrix(Vector((0, 0, 0)), Vector(
            (0, 0, 1)), Vector((0, 1, 0)), False, True)
    else:
        mat = self._object.matrix_world.normalized()

    pos_vec = Vector((0, 0, 0))
    neg_vec = Vector((0, 0, 0))
    pos_vec[self.translate_axis] = 1.0
    neg_vec[self.translate_axis] = -1.0

    pos_vec = (mat @ pos_vec) - mat.translation
    neg_vec = (mat @ neg_vec) - mat.translation

    if pos_vec.angle(view_vec) < neg_vec.angle(view_vec):
        side = -1
    else:
        side = 1

    # if self.translate_axis == 1:
    #     side *= -1
    return side


#
# MODAL
#
def cache_point_data(self):
    self._object.data.calc_normals_split()

    vert_amnt = len(self._object.data.vertices)
    edge_amnt = len(self._object.data.edges)
    loop_amnt = len(self._object.data.loops)
    face_amnt = len(self._object.data.polygons)

    self._container.og_sharp = np.zeros(edge_amnt, dtype=bool)
    self._object.data.edges.foreach_get(
        'use_edge_sharp', self._container.og_sharp)

    self._container.og_seam = np.zeros(edge_amnt, dtype=bool)
    self._object.data.edges.foreach_get('use_seam', self._container.og_seam)

    self._container.og_norms = np.zeros(loop_amnt*3, dtype=np.float32)
    self._object.data.loops.foreach_get('normal', self._container.og_norms)
    self._container.og_norms.shape = [loop_amnt, 3]

    self._container.new_norms = self._container.og_norms.copy()
    self._container.cache_norms = self._container.og_norms.copy()

    max_link_eds = max([len(v.link_edges) for v in self._object_bm.verts])
    max_link_loops = max([len(v.link_loops) for v in self._object_bm.verts])
    max_link_f_vs = max([len(f.verts) for f in self._object_bm.faces])
    max_link_f_loops = max([len(f.loops) for f in self._object_bm.faces])

    link_vs = []
    link_ls = []
    for v in self._object_bm.verts:
        l_v_inds = [-1] * max_link_eds
        l_l_inds = [-1] * max_link_loops

        for e, ed in enumerate(v.link_edges):
            l_v_inds[e] = ed.other_vert(v).index

        for l, loop in enumerate(v.link_loops):
            l_l_inds[l] = loop.index

        link_vs += l_v_inds
        link_ls += l_l_inds

    self._container.vert_link_vs = np.array(link_vs, dtype=np.int32)
    self._container.vert_link_vs.shape = [vert_amnt, max_link_eds]

    self._container.vert_link_ls = np.array(link_ls, dtype=np.int32)
    self._container.vert_link_ls.shape = [vert_amnt, max_link_loops]

    link_f_vs = []
    link_f_ls = []
    for f in self._object_bm.faces:
        l_v_inds = [-1] * max_link_f_vs
        l_l_inds = [-1] * max_link_f_loops

        for v, vert in enumerate(f.verts):
            l_v_inds[v] = vert.index

        for l, loop in enumerate(f.loops):
            l_l_inds[l] = loop.index

        link_f_vs += l_v_inds
        link_f_ls += l_l_inds

    self._container.face_link_vs = np.array(link_f_vs, dtype=np.int32)
    self._container.face_link_vs.shape = [face_amnt, max_link_f_vs]

    self._container.face_link_ls = np.array(link_f_ls, dtype=np.int32)
    self._container.face_link_ls.shape = [face_amnt, max_link_f_loops]

    self._container.po_coords = np.array(
        [v.co for v in self._object_bm.verts], dtype=np.float32)
    self._container.loop_coords = np.array(
        [self._object_bm.verts[l.vertex_index].co for l in self._object.data.loops], dtype=np.float32)

    loop_tri_cos = [[] for i in range(loop_amnt)]
    for v in self._object_bm.verts:
        ed_inds = [ed.index for ed in v.link_edges]
        for loop in v.link_loops:
            loop_cos = [v.co+v.normal*.001]
            for ed in loop.face.edges:
                if ed.index in ed_inds:
                    ov = ed.other_vert(v)
                    vec = (ov.co+ov.normal*.001) - (v.co+v.normal*.001)

                    loop_cos.append((v.co+v.normal*.001) + vec * 0.5)

            loop_tri_cos[loop.index] = loop_cos

    self._container.loop_tri_coords = np.array(loop_tri_cos, dtype=np.float32)

    #
    #

    loop_sel = [False] * loop_amnt
    loop_hide = [True] * loop_amnt
    loop_act = [False] * loop_amnt
    for v in self._object_bm.verts:
        ed_inds = [ed.index for ed in v.link_edges]
        if len(v.link_loops) > 0:
            loop_inds = [l.index for l in v.link_loops]
            loop_f_inds = [l.face.index for l in v.link_loops]
            loop_norms = [
                self._object.data.loops[l.index].normal for l in v.link_loops]

            loop_tri_cos = []
            for loop in v.link_loops:
                loop_cos = [v.co+v.normal*.001]
                for ed in loop.face.edges:
                    if ed.index in ed_inds:
                        ov = ed.other_vert(v)
                        vec = (ov.co+ov.normal*.001) - (v.co+v.normal*.001)

                        loop_cos.append((v.co+v.normal*.001) + vec * 0.5)
                loop_tri_cos.append(loop_cos)

            po = self._container.add_point(
                v.co, v.normal, loop_norms, loop_inds, loop_f_inds, loop_tri_cos)

            # Vertex selection
            if bpy.context.tool_settings.mesh_select_mode[0]:
                po.set_select(v.select)

                for l_ind in loop_inds:
                    loop_sel[l_ind] = v.select

        else:
            po = self._container.add_empty_point(
                v.co, Vector((0, 0, 1)))

        for loop in po.loops:
            loop_hide[loop.loop_index] = v.hide
        po.set_hide(v.hide)

    # Edge selection
    if bpy.context.tool_settings.mesh_select_mode[1]:
        for ed in self._object_bm.edges:
            if ed.select:
                for v in ed.verts:
                    if self._individual_loops:
                        for loop in self._container.points[v.index].loops:
                            if loop.face_index in [ed.link_faces[0].index, ed.link_faces[1].index]:
                                loop.set_select(True)
                                loop_sel[loop.loop_index] = True

                    else:
                        self._container.points[v.index].set_select(True)
                        for loop in self._container.points[v.index].loops:
                            loop_sel[loop.loop_index] = True

    # Face selection
    if bpy.context.tool_settings.mesh_select_mode[2]:
        for f in self._object_bm.faces:
            if f.select:
                for v in f.verts:
                    if self._individual_loops:
                        for loop in self._container.points[v.index].loops:
                            if loop.face_index == f.index:
                                loop.set_select(True)
                                loop_sel[loop.loop_index] = True
                    else:
                        self._container.points[v.index].set_select(True)
                        for loop in self._container.points[v.index].loops:
                            loop_sel[loop.loop_index] = True

    self._container.hide_status = np.array(loop_hide, dtype=bool)
    self._container.sel_status = np.array(loop_sel, dtype=bool)
    self._container.act_status = np.array(loop_act, dtype=bool)

    cache_mirror_data(self)
    return


def cache_mirror_data(self):
    x_mirs = []
    y_mirs = []
    z_mirs = []

    for loop in self._object.data.loops:
        po = self._container.points[loop.vertex_index]

        for i in range(3):
            # Get mirrored coordinate converting to local, mirroring, then going back to world
            co = self._object.matrix_world.inverted() @ po.co
            co[i] *= -1
            co = self._object.matrix_world @ co

            result = self._object_kd.find_range(co, self._mirror_range)

            m_po = None
            for res in result:
                o_po = self._container.points[res[1]]
                if o_po.valid:
                    m_po = o_po
                    break

            if m_po != None:
                norms, tangs = get_po_loop_data(self, m_po)

                cur_loop = po.loops[[
                    l.index for l in po.loops if l.loop_index == loop.index][0]]

                m_ind = match_loops_vecs(
                    self, cur_loop, tangs, flip_axis=i)

                if i == 0:
                    x_mirs.append(m_po.loops[m_ind].loop_index)
                if i == 1:
                    y_mirs.append(m_po.loops[m_ind].loop_index)
                if i == 2:
                    z_mirs.append(m_po.loops[m_ind].loop_index)

            else:
                if i == 0:
                    x_mirs.append(loop.index)
                if i == 1:
                    y_mirs.append(loop.index)
                if i == 2:
                    z_mirs.append(loop.index)

    self.mir_loops_x = np.array(x_mirs, dtype=np.float32)
    self.mir_loops_x = np.array(y_mirs, dtype=np.float32)
    self.mir_loops_x = np.array(z_mirs, dtype=np.float32)
    return


def update_filter_weights(self):
    abn_props = bpy.context.scene.abnormal_props

    weights = [1.0] * len(self._object.data.loops)
    if abn_props.vertex_group != '':
        if abn_props.vertex_group in self._object.vertex_groups:
            for po in self._container.points:
                vg = self._object.vertex_groups[abn_props.vertex_group]

                try:
                    for loop in po.loops:
                        weights[loop.loop_index] = vg.weight(po.index)

                except:
                    for loop in po.loops:
                        weights[loop.loop_index] = 0.0

        else:
            abn_props.vertex_group = ''

    self._container.filter_weights = np.array(weights)[:, None]
    return


def init_nav_list(self):
    self.nav_list = [['LEFTMOUSE', 'CLICK', True, False, False, False],
                     ['LEFTMOUSE', 'PRESS', True, False, False, False],
                     ['LEFTMOUSE', 'RELEASE', True, False, False, False],
                     ['MOUSEMOVE', 'PRESS', True, False, False, False],
                     ['MOUSEMOVE', 'RELEASE', True, False, False, False],
                     ['WHEELUPMOUSE', 'PRESS', True, False, False, False],
                     ['WHEELDOWNMOUSE', 'PRESS', True, False, False, False],
                     ['N', 'PRESS', True, False, False, False],
                     ['MIDDLEMOUSE', 'PRESS', True, False, False, False], ]

    names = ['Zoom View', 'Rotate View', 'Pan View', 'Dolly View',
             'View Selected', 'View Camera Center', 'View All', 'View Axis',
             'View Orbit', 'View Roll', 'View Persp/Ortho', 'Frame Selected']

    config = bpy.context.window_manager.keyconfigs.get('blender')
    if config:
        for item in config.keymaps['3D View'].keymap_items:
            if item.name in names:
                item_dat = [item.type, item.value, item.any,
                            item.ctrl, item.shift, item.alt]
                if item_dat not in self.nav_list:
                    self.nav_list.append(item_dat)

    config = bpy.context.window_manager.keyconfigs.get('blender user')
    if config:
        for item in config.keymaps['3D View'].keymap_items:
            if item.name in names:
                item_dat = [item.type, item.value, item.any,
                            item.ctrl, item.shift, item.alt]
                if item_dat not in self.nav_list:
                    self.nav_list.append(item_dat)

    return


def ob_data_structures(self, ob):
    if ob.data.shape_keys != None:
        for sk in ob.data.shape_keys.key_blocks:
            self._objects_sk_vis.append(sk.mute)
            sk.mute = True

    bm = create_simple_bm(self, ob)

    bvh = BVHTree.FromBMesh(bm)

    kd = create_kd(bm)

    return bm, kd, bvh


def add_to_undostack(self, stack_type):
    if stack_type == 0:
        sel_status = self._container.get_selected_loops()
        vis_status = self._container.get_visible_loops()

        if self._history_position > 0:
            while self._history_position > 0:
                self._history_stack.pop(0)
                self._history_position -= 1

        if len(self._history_stack)+1 > self._history_steps:
            self._history_stack.pop(-1)
        self._history_stack.insert(0, [stack_type, sel_status, vis_status])

        self.redraw = True
        update_orbit_empty(self)

    else:
        cur_normals = self._container.get_current_normals()
        if self._history_position > 0:
            while self._history_position > 0:
                self._history_stack.pop(0)
                self._history_position -= 1

        if len(self._history_stack)+1 > self._history_steps:
            self._history_stack.pop(-1)
        self._history_stack.insert(0, [stack_type, cur_normals])

    return


def move_undostack(self, dir):
    if dir > 0 and len(self._history_stack)-1 > self._history_position or dir < 0 and self._history_position > 0:
        self._history_position += dir

        state_type = self._history_stack[self._history_position][0]
        state = self._history_stack[self._history_position][1]

        if state_type == 0:
            vis_state = self._history_stack[self._history_position][2]
            for po in self._container.points:
                po.set_hide(True)

            for ind in vis_state:
                po = self._container.points[ind[0]]
                if po.valid:
                    loop = po.loops[ind[1]]
                    loop.set_hide(False)

                po.set_hidden_from_loops()

            for po in self._container.points:
                po.set_select(False)

            for ind in state:
                po = self._container.points[ind[0]]
                if po.hide == False and po.valid:
                    loop = po.loops[ind[1]]
                    if loop.hide == False:
                        loop.set_select(True)

                po.set_selection_from_loops()

            if self._active_point != None:
                if self._active_point.select == False:
                    self._container.clear_active()
                    self._active_point = None

            update_orbit_empty(self)
            self.redraw = True

        if state_type == 1:
            for po in self._container.points:
                for loop in po.loops:
                    loop.normal = state[po.index][loop.index].copy()

            self.redraw = True
            set_new_normals(self)

    return


def img_load(img_name, path):
    script_file = os.path.realpath(path)
    directory = os.path.dirname(script_file)

    img_fp = directory.replace('/', '\\') + '\\' + img_name

    not_there = True
    for img in bpy.data.images:
        if img.filepath == img_fp:
            not_there = False
            break

    if not_there:
        img = bpy.data.images.load(img_fp)
    img.colorspace_settings.name = 'Raw'

    if img.gl_load():
        raise Exception()

    return img


def finish_modal(self, restore):
    self._behavior_prefs.rotate_gizmo_use = self._use_gizmo
    self._display_prefs.gizmo_size = self._gizmo_size
    self._display_prefs.normal_size = self._normal_size
    self._display_prefs.line_brightness = self._line_brightness
    self._display_prefs.point_size = self._point_size
    self._display_prefs.loop_tri_size = self._loop_tri_size
    self._display_prefs.selected_only = self._selected_only
    self._display_prefs.selected_scale = self._selected_scale
    self._behavior_prefs.individual_loops = self._individual_loops
    self._display_prefs.ui_scale = self._ui_scale
    self._display_prefs.display_wireframe = self._use_wireframe_overlay

    if bpy.context.area != None:
        if bpy.context.area.type == 'VIEW_3D':
            for space in bpy.context.area.spaces:
                if space.type == 'VIEW_3D':
                    space.show_region_toolbar = self._reg_header
                    space.show_region_ui = self._reg_ui
                    space.overlay.show_cursor = self._cursor
                    space.overlay.show_wireframes = self._wireframe
                    space.overlay.wireframe_threshold = self._thresh
                    space.overlay.show_text = self._text

    bpy.context.window.cursor_modal_set('DEFAULT')

    clear_drawing(self)

    if restore:
        ob = self._object
        if ob.as_pointer() != self._object_pointer:
            for o_ob in bpy.data.objects:
                if o_ob.as_pointer() == self._object_pointer:
                    ob = o_ob

        self._object.data.edges.foreach_set(
            'use_edge_sharp', self._container.og_sharp)

        # restore normals
        og_norms = [None for l in ob.data.loops]
        for po in self._container.points:
            for loop in po.loops:
                og_norms[loop.loop_index] = loop.og_normal.normalized()
        ob.data.normals_split_custom_set(og_norms)

    restore_modifiers(self)

    abn_props = bpy.context.scene.abnormal_props
    abn_props.object = ''

    delete_orbit_empty(self)
    if self._target_emp != None:
        try:
            bpy.data.objects.remove(self._target_emp)
        except:
            self._target_emp = None

    self._object.select_set(True)
    bpy.context.view_layer.objects.active = self._object
    return


def restore_modifiers(self):
    if self._object.data.shape_keys != None:
        for s in range(len(self._object.data.shape_keys.key_blocks)):
            self._object.data.shape_keys.key_blocks[s].mute = self._objects_sk_vis[s]

    # restore modifier status
    for m, mod_dat in enumerate(self._objects_mod_status):
        for mod in self._object.modifiers:
            if mod.name == self._objects_mod_status[m][2]:
                mod.show_viewport = self._objects_mod_status[m][0]
                mod.show_render = self._objects_mod_status[m][1]
                break

    return


def check_area(self):
    # # inside region check
    # if self._mouse_reg_loc[0] >= 0.0 and self._mouse_reg_loc[0] <= bpy.context.area.width and self._mouse_reg_loc[1] >= 0.0 and self._mouse_reg_loc[1] <= bpy.context.area.height:
    #     return bpy.context.region, bpy.context.region_data

    # # if not inside check other areas to find if we are in another region that is a valid view_3d and return that ones data
    # for area in bpy.context.screen.areas:
    #     if area.type == 'VIEW_3D' and area != self._draw_area:
    #         if area.spaces.active.type == 'VIEW_3D':
    #             if self._mouse_abs_loc[0] > area.x and self._mouse_abs_loc[0] < area.x+area.width and self._mouse_abs_loc[1] > area.y and self._mouse_abs_loc[1] < area.y+area.height:
    #                 for region in area.regions:
    #                     if region.type == 'WINDOW':
    #                         return region, area.spaces.active.region_3d

    return bpy.context.region, bpy.context.region_data


#
# GIZMO
#
def gizmo_click_init(self, event, giz_status):
    if self._use_gizmo:
        sel_inds = self._container.get_selected_loops()
        if event.alt == False:
            if len(sel_inds) == 0:
                return True

        self._mode_cache.clear()

        # Cache current normals before rotation starts and setup gizmo as being used
        if event.alt == False:
            self._container.cache_current_normals()

            for gizmo in self._window.gizmo_sets[giz_status[1]].gizmos:
                if gizmo.index != giz_status[2]:
                    gizmo.active = False
                else:
                    gizmo.in_use = True

        orb_mat = self._orbit_ob.matrix_world

        view_vec = view3d_utils.region_2d_to_vector_3d(self.act_reg, self.act_rv3d, Vector(
            (self._mouse_reg_loc[0], self._mouse_reg_loc[1])))
        view_orig = view3d_utils.region_2d_to_origin_3d(
            self.act_reg, self.act_rv3d, Vector((self._mouse_reg_loc[0], self._mouse_reg_loc[1])))

        line_a = view_orig
        line_b = view_orig + view_vec*10000

        # Project cursor from view onto the rotation axis plane
        if giz_status[0] == 'ROT_X':
            giz_vec = orb_mat @ Vector((1, 0, 0)) - orb_mat.translation
            self.translate_axis = 0

        if giz_status[0] == 'ROT_Y':
            giz_vec = orb_mat @ Vector((0, 1, 0)) - orb_mat.translation
            self.translate_axis = 1

        if giz_status[0] == 'ROT_Z':
            giz_vec = orb_mat @ Vector((0, 0, 1)) - orb_mat.translation
            self.translate_axis = 2

        mouse_co_3d = intersect_line_plane(
            line_a, line_b, orb_mat.translation, giz_vec)
        mouse_co_local = orb_mat.inverted() @ mouse_co_3d

        # Get start angle for rotation
        if giz_status[0] == 'ROT_X':
            test_vec = mouse_co_local.yz

        if giz_status[0] == 'ROT_Y':
            test_vec = mouse_co_local.xz

        if giz_status[0] == 'ROT_Z':
            test_vec = mouse_co_local.xy

        self.translate_mode = 2
        ang_offset = Vector((0, 1)).angle_signed(test_vec)
        self._mode_cache.append(test_vec)
        # Add cache data for tool mode
        if event.alt == False:
            self._window.update_gizmo_rot(0, -ang_offset)
            self._mode_cache.append(sel_inds)
            self._mode_cache.append(0)
            self._mode_cache.append(-ang_offset)
            self._mode_cache.append(orb_mat.copy())
            self._mode_cache.append(True)
        else:
            self._mode_cache.append([])
            self._mode_cache.append(0)
            self._mode_cache.append(-ang_offset)
            self._mode_cache.append(orb_mat.copy())
            self._mode_cache.append(False)

        self.gizmo_click = True
        self._current_tool = self._gizmo_tool
        self.tool_mode = True
        start_active_drawing(self)

        return False
    return True


def relocate_gizmo_panel(self):
    rco = view3d_utils.location_3d_to_region_2d(
        self.act_reg, self.act_rv3d, self._orbit_ob.location)

    if rco != None:
        self._gizmo_panel.set_new_position(
            [rco[0]+self.gizmo_reposition_offset[0], rco[1]+self.gizmo_reposition_offset[1]], self._window.dimensions)
    return


def gizmo_update_hide(self, status):
    if self._use_gizmo == False:
        status = False

    self._gizmo_panel.set_visibility(status)
    self._rot_gizmo.set_visibility(status)
    return


#
# MODES
#
def add_target_empty(ob):
    emp = bpy.data.objects.new('ABN_Target Empty', None)
    emp.empty_display_size = 0.0
    emp.show_in_front = True
    emp.matrix_world = ob.matrix_world.copy()
    emp.empty_display_type = 'SPHERE'
    bpy.context.collection.objects.link(emp)

    return emp


def start_sphereize_mode(self):
    update_filter_weights(self)

    for i in range(len(bpy.context.selected_objects)):
        bpy.context.selected_objects[0].select_set(False)

    sel_cos = self._container.get_selected_loop_cos()
    avg_loc = average_vecs(sel_cos)
    self._target_emp.location = avg_loc
    self._target_emp.empty_display_size = 0.5
    self._target_emp.select_set(True)
    bpy.context.view_layer.objects.active = self._target_emp

    sel_inds = self._container.get_selected_loops()
    self._mode_cache.append(sel_inds)
    self._mode_cache.append(avg_loc)

    self._container.cache_current_normals()

    gizmo_update_hide(self, False)
    self.sphereize_mode = True
    self.tool_mode = True
    self._current_tool = self._sphereize_tool

    keymap_target(self)
    # self._export_panel.set_visibility(False)
    self._tools_panel.set_visibility(False)
    self._sphere_panel.set_visibility(True)
    self._sphere_panel.set_new_position(
        self._mouse_reg_loc, window_dims=self._window.dimensions)

    sphereize_normals(self, sel_inds)
    return


def end_sphereize_mode(self, keep_normals):
    if keep_normals == False:
        self._container.restore_cached_normals()
        set_new_normals(self)

    # self._export_panel.set_visibility(True)
    self._tools_panel.set_visibility(True)
    self._sphere_panel.set_visibility(False)

    add_to_undostack(self, 1)
    self.translate_axis = 2
    self.translate_mode = 0
    clear_translate_axis_draw(self)
    self._target_emp.empty_display_size = 0.0
    self._target_emp.select_set(False)
    self._orbit_ob.select_set(True)
    bpy.context.view_layer.objects.active = self._orbit_ob

    gizmo_update_hide(self, True)

    self.sphereize_mode = False
    self.tool_mode = False
    self._mode_cache.clear()
    keymap_refresh(self)
    return


def sphereize_normals(self, sel_inds):
    for i, ind in enumerate(sel_inds):
        po = self._container.points[ind[0]]
        loop = po.loops[ind[1]]

        if po.valid:
            vec = (self._object.matrix_world.inverted() @ po.co) - \
                (self._object.matrix_world.inverted() @ self._target_emp.location)

            loop_norm_set(
                self, loop, loop.cached_normal, loop.cached_normal.lerp(vec, self.target_strength))

            self.redraw_active = True

    set_new_normals(self)
    return


def start_point_mode(self):
    update_filter_weights(self)

    for i in range(len(bpy.context.selected_objects)):
        bpy.context.selected_objects[0].select_set(False)

    sel_cos = self._container.get_selected_loop_cos()
    avg_loc = average_vecs(sel_cos)
    self._target_emp.location = avg_loc
    self._target_emp.empty_display_size = 0.5
    self._target_emp.select_set(True)
    bpy.context.view_layer.objects.active = self._target_emp

    sel_inds = self._container.get_selected_loops()
    self._mode_cache.append(sel_inds)
    self._mode_cache.append(avg_loc)

    self._container.cache_current_normals()

    gizmo_update_hide(self, False)
    self.point_mode = True
    self.tool_mode = True
    self._current_tool = self._point_tool

    keymap_target(self)
    # self._export_panel.set_visibility(False)
    self._tools_panel.set_visibility(False)
    self._point_panel.set_visibility(True)
    self._point_panel.set_new_position(
        self._mouse_reg_loc, window_dims=self._window.dimensions)

    point_normals(self, sel_inds)
    return


def end_point_mode(self, keep_normals):
    if keep_normals == False:
        self._container.restore_cached_normals()
        set_new_normals(self)

    # self._export_panel.set_visibility(True)
    self._tools_panel.set_visibility(True)
    self._point_panel.set_visibility(False)

    add_to_undostack(self, 1)
    self.translate_axis = 2
    self.translate_mode = 0
    clear_translate_axis_draw(self)
    self._target_emp.empty_display_size = 0.0
    self._target_emp.select_set(False)
    self._orbit_ob.select_set(True)
    bpy.context.view_layer.objects.active = self._orbit_ob

    gizmo_update_hide(self, True)

    self.point_mode = False
    self.tool_mode = False
    self._mode_cache.clear()
    keymap_refresh(self)
    return


def point_normals(self, sel_inds):
    if self.point_align:
        sel_cos = self._container.get_selected_loop_cos()
        avg_loc = average_vecs(sel_cos)
        vec = (self._object.matrix_world.inverted() @ self._target_emp.location) - \
            (self._object.matrix_world.inverted() @ avg_loc)

    for i, ind in enumerate(sel_inds):
        po = self._container.points[ind[0]]
        loop = po.loops[ind[1]]

        if po.valid:
            if self.point_align == False:
                vec = (self._object.matrix_world.inverted(
                ) @ self._target_emp.location) - (self._object.matrix_world.inverted() @ po.co)

            loop_norm_set(
                self, loop, loop.cached_normal, loop.cached_normal.lerp(vec, self.target_strength))

            self.redraw_active = True

    set_new_normals(self)
    return


def move_target(self, shift):
    offset = [self._mouse_reg_loc[0] - self._mode_cache[2]
              [0], self._mouse_reg_loc[1] - self._mode_cache[2][1]]

    if shift:
        offset[0] = offset[0]*.1
        offset[1] = offset[1]*.1

    self._mode_cache[4][0] = self._mode_cache[4][0] + offset[0]
    self._mode_cache[4][1] = self._mode_cache[4][1] + offset[1]

    new_co = view3d_utils.region_2d_to_location_3d(
        self.act_reg, self.act_rv3d, self._mode_cache[4], self._mode_cache[3])
    if self.translate_mode == 0:
        self._target_emp.location = new_co

    elif self.translate_mode == 1:
        self._target_emp.location = self._mode_cache[3].copy()
        self._target_emp.location[self.translate_axis] = new_co[self.translate_axis]

    elif self.translate_mode == 2:
        loc_co = self._object.matrix_world.inverted() @ new_co
        def_dist = loc_co[self.translate_axis]

        def_vec = Vector((0, 0, 0))
        def_vec[self.translate_axis] = def_dist

        def_vec = (self._object.matrix_world @ def_vec) - \
            self._object.matrix_world.translation

        self._target_emp.location = self._mode_cache[3].copy()
        self._target_emp.location += def_vec

    return


#
# SELECTION
#
def clear_active_face(self):
    if self._active_face != None:
        self._container.clear_active()

    self._active_face = None
    return


def get_active_point_index(indeces, active):
    if active == None or active.type != 'POINT':
        return None

    for i, ind in enumerate(indeces):
        if active.index == ind:
            return i

    return None


def get_active_loop_index(indeces, active):
    if active == None or active.type != 'LOOP':
        return None

    for i, ind_set in enumerate(indeces):
        if active.point.index == ind_set[0] and active.index == ind_set[1]:
            return i

    return None


def selection_test(self, shift, radius=6.0):
    # Get coords in region space
    rcos = get_np_region_cos(self._container.po_coords,
                             self.act_reg, self.act_rv3d)

    # Get ordered list of closest points within the threshold
    d_order = get_np_vec_ordered_dists(
        rcos, [self._mouse_reg_loc[0], self._mouse_reg_loc[1], 0.0], threshold=15.0)

    change = False
    v_ls = self._container.vert_link_ls
    # Point selection
    if d_order.size > 0:
        # Test for first point that is non occluded if xray off
        if self._x_ray_mode == False:
            po_ind = None
            for ind in d_order:
                valid_po = not ray_cast_view_occlude_test(
                    Vector(self._container.po_coords[ind]), self._mouse_reg_loc, self._object_bvh, self.act_reg, self.act_rv3d)
                if valid_po:
                    po_ind = ind
                    break
        else:
            po_ind = d_order[0]

        if po_ind != None:
            mask = v_ls[po_ind]
            mask = mask[mask >= 0]

            # Clear all selection and set points loops as sel and active
            if shift == False:
                self._container.sel_status[:] = False
                self._container.act_status[:] = False

                self._container.sel_status[mask] = True
                self._container.act_status[mask] = True

            # Adding to selection
            else:
                po_sel = self._container.sel_status[mask]
                po_act = self._container.act_status[mask]

                # Check if any point loops are not sel/act if so make all sel/act
                if po_sel.all() == False or po_act.all() == False:
                    self._container.sel_status[mask] = True
                    self._container.act_status[:] = False
                    self._container.act_status[mask] = True

                # If all loops neither act/sel then all loops are sel/act so clear both
                else:
                    self._container.sel_status[mask] = False
                    self._container.act_status[:] = False

            change = True

    # No point selection so try loop tri selection if available as an option
    elif self._individual_loops:
        change = True

    # No valid selection so try test face
    if change == False:
        face_res = ray_cast_to_mouse(self)
        if face_res != None:
            # Only test loops of the face
            if self._individual_loops:
                f_ls = self._container.face_link_ls
                mask = f_ls[face_res[1]]
                mask = mask[mask >= 0]
            # Test each verts loops of the face
            else:
                f_vs = self._container.face_link_vs
                mask = v_ls[f_vs[face_res[1]]]
                mask = mask[mask >= 0]

            # New selection so clear act and sel and set current as sel/act
            if shift == False:
                self._container.sel_status[:] = False
                self._container.act_status[:] = False

                self._container.sel_status[mask] = True
                self._container.act_status[mask] = True

            # Adding to selection
            else:
                l_sel = self._container.sel_status[mask]
                l_act = self._container.act_status[mask]

                # Check if any face loops are not sel/act if so make all sel/act
                if l_sel.all() == False or l_act.all() == False:
                    self._container.sel_status[mask] = True
                    self._container.act_status[:] = False
                    self._container.act_status[mask] = True

                # If all loops neither act/sel then all loops are sel/act so clear both
                else:
                    self._container.sel_status[mask] = False
                    self._container.act_status[:] = False

            #

            self._active_face = face_res[1]
            change = True

    return change


def loop_selection_test(self, shift, radius=6.0):
    change = False
    clear_active_face(self)

    face_res = ray_cast_to_mouse(self)
    if face_res != None:
        if shift == False:
            for po in self._container.points:
                po.set_select(False)

        face_rco = view3d_utils.location_3d_to_region_2d(
            self.act_reg, self.act_rv3d, face_res[0])

        sel_ed = None
        small_dist = 0.0
        dist_2d = 0.0
        for ed in self._object_bm.faces[face_res[1]].edges:
            # then find nearest point on those edges that are in range
            nearest_point_co, nearest_point_dist = nearest_co_on_line(
                face_res[0], ed.verts[0].co, ed.verts[1].co)

            if nearest_point_dist < small_dist or sel_ed == None:
                sel_ed = ed
                small_dist = nearest_point_dist

                near_rco = view3d_utils.location_3d_to_region_2d(
                    self.act_reg, self.act_rv3d, nearest_point_co)

                dist_2d = (near_rco - face_rco).length

        if sel_ed != None:
            # Edge loop selection
            if dist_2d < 12.0:
                skip_vs = [
                    po.index for po in self._container.points if po.hide and po.valid]

                sel_loop = get_edge_loop(
                    self._object_bm, sel_ed, skip_verts=skip_vs)

                v_inds = []
                for ed_ind in sel_loop:
                    for v in self._object_bm.edges[ed_ind].verts:
                        if v.index not in v_inds:
                            v_inds.append(v.index)

                cur_sel = [
                    self._container.points[ind].select for ind in v_inds]

                loop_status = False in cur_sel
                for ind in v_inds:
                    self._container.points[ind].set_select(
                        loop_status)
                    change = True

            # Face loop selection
            else:
                skip_fs = set()
                if self._individual_loops:
                    for po in self._container.points:
                        if po.valid:
                            for loop in po.loops:
                                if loop.hide or po.hide:
                                    skip_fs.add(loop.face_index)
                else:
                    for po in self._container.points:
                        if po.hide and po.valid:
                            for loop in po.loops:
                                skip_fs.add(loop.face_index)

                sel_loop = get_face_loop(
                    self._object_bm, sel_ed, skip_fs=list(skip_fs))

                v_inds = []
                for f_ind in sel_loop:
                    for v in self._object_bm.faces[f_ind].verts:
                        if v.index not in v_inds:
                            v_inds.append(v.index)

                if self._individual_loops:
                    cur_sel = []
                    for ind in v_inds:
                        for loop in self._container.points[ind].loops:
                            if loop.face_index in sel_loop:
                                cur_sel.append(loop.select)
                else:
                    cur_sel = [
                        self._container.points[ind].select for ind in v_inds]

                loop_status = False in cur_sel
                for ind in v_inds:
                    if self._individual_loops:
                        for loop in self._container.points[ind].loops:
                            if loop.face_index in sel_loop:
                                loop.set_select(loop_status)
                    else:
                        self._container.points[ind].set_select(
                            loop_status)
                    change = True

    return change


def path_selection_test(self, shift, radius=6.0):
    change = False

    face_res = ray_cast_to_mouse(self)
    if face_res != None:
        if shift == False:
            for po in self._container.points:
                po.set_select(False)

        if self._active_face != None:
            path_f = find_path_between_faces(
                [self._active_face, face_res[1]], self._object_bm)

            clear_active_face(self)
            self._active_face = face_res[1]
            if self._individual_loops:
                self._container.select_face_loops(
                    face_res[1], set_active=True)
            else:
                self._container.select_face_verts(
                    face_res[1], set_active=True)

            for ind in path_f:
                for v in self._object_bm.faces[ind].verts:
                    if self._individual_loops:
                        for loop in self._container.points[v.index].loops:
                            if loop.face_index == ind:
                                loop.set_select(True)
                    else:
                        self._container.points[v.index].set_select(True)

        else:
            near_ind = self._object_kd.find(face_res[0])
            path_v, path_ed = find_path_between_verts(
                [self._active_point.index, near_ind[1]], self._object_bm)

            for ind in path_v:
                self._container.points[ind].set_select(True)

            self._container.points[near_ind[1]].set_select(True)
            self._container.set_active_point(near_ind[1])
            self._active_point = self._container.points[near_ind[1]]
            clear_active_face(self)

        change = True

    return change


def box_selection_test(self, shift, ctrl):
    add_rem_status = 0
    if ctrl:
        add_rem_status = 2
    else:
        if shift:
            add_rem_status = 1

    clear_active_face(self)

    avail_cos, avail_sel_status, avail_inds = self._container.get_selection_available(
        add_rem_status)

    loop_switch_pont = len(avail_inds)
    # Add in loop selection data if enabled
    if self._individual_loops:
        avail_tri_cos, avail_loop_sel_status, avail_loop_inds = self._container.get_loop_selection_available(
            add_rem_status)
        avail_cos += avail_tri_cos
        avail_sel_status += avail_loop_sel_status
        avail_inds += avail_loop_inds

    face_switch_pont = len(avail_inds)
    avail_cos += [f.calc_center_median() for f in self._object_bm.faces]
    if add_rem_status == 2:
        avail_sel_status += [True for i in self._object_bm.faces]
    else:
        avail_sel_status += [False for i in self._object_bm.faces]
    avail_inds += [i.index for i in self._object_bm.faces]

    change, unselect, new_active, new_sel_add, new_sel_remove = box_points_selection_test(
        avail_cos, avail_sel_status, self._mouse_reg_loc, self._mode_cache[0][0], self.act_reg, self.act_rv3d, add_rem_status, self._x_ray_mode, self._object_bvh)

    if change:
        if unselect:
            for po in self._container.points:
                po.set_select(False)

        for i, ind in enumerate(new_sel_add + new_sel_remove):
            status = True
            if i >= len(new_sel_add):
                status = False

            po_ind = avail_inds[ind]
            if ind < loop_switch_pont:
                self._container.points[po_ind].set_select(status)
            elif ind >= face_switch_pont:
                if self._individual_loops:
                    self._container.set_face_loops_select(
                        po_ind, status)
                else:
                    self._container.set_face_verts_select(
                        po_ind, status)
            else:
                self._container.points[po_ind[0]
                                       ].loops[po_ind[1]].set_select(status)
                self._container.points[po_ind[0]
                                       ].set_selection_from_loops()

        if self._active_point != None:
            if self._active_point.select == False:
                self._container.clear_active()
                self._active_point = None

                # if self._container.points[self._active_point[0]].select == False:
                #     self._active_point = None

    return change


def circle_selection_test(self, shift, ctrl, radius):
    add_rem_status = 0
    if ctrl:
        add_rem_status = 2
    else:
        if shift:
            add_rem_status = 1

    clear_active_face(self)

    avail_cos, avail_sel_status, avail_inds = self._container.get_selection_available(
        add_rem_status)

    loop_switch_pont = len(avail_inds)
    # Add in loop selection data if enabled
    if self._individual_loops:
        avail_loop_cos, avail_loop_sel_status, avail_loop_inds = self._container.get_loop_selection_available(
            add_rem_status)

        avail_cos += avail_loop_cos
        avail_sel_status += avail_loop_sel_status
        avail_inds += avail_loop_inds

    face_switch_pont = len(avail_inds)
    avail_cos += [f.calc_center_median() for f in self._object_bm.faces]
    if add_rem_status == 2:
        avail_sel_status += [True for i in self._object_bm.faces]
    else:
        avail_sel_status += [False for i in self._object_bm.faces]
    avail_inds += [i.index for i in self._object_bm.faces]

    change, unselect, new_active, new_sel, new_sel_status = circle_points_selection_test(
        avail_cos, avail_sel_status, self._mouse_reg_loc, radius, self.act_reg, self.act_rv3d, add_rem_status, self._x_ray_mode, self._object_bvh)

    if change:
        for ind in new_sel:
            po_ind = avail_inds[ind]
            if ind < loop_switch_pont:
                self._container.points[po_ind].set_select(
                    new_sel_status)
            elif ind >= face_switch_pont:
                if self._individual_loops:
                    self._container.set_face_loops_select(
                        po_ind, new_sel_status)
                else:
                    self._container.set_face_verts_select(
                        po_ind, new_sel_status)
            else:
                self._container.points[po_ind[0]
                                       ].loops[po_ind[1]].set_select(new_sel_status)
                self._container.points[po_ind[0]
                                       ].set_selection_from_loops()

        if self._active_point != None:
            if self._active_point.select == False:
                self._container.clear_active()
                self._active_point = None

    return change


def lasso_selection_test(self, shift, ctrl):
    add_rem_status = 0
    if ctrl:
        add_rem_status = 2
    else:
        if shift:
            add_rem_status = 1

    clear_active_face(self)

    avail_cos, avail_sel_status, avail_inds = self._container.get_selection_available(
        add_rem_status)

    loop_switch_pont = len(avail_inds)
    # Add in loop selection data if enabled
    if self._individual_loops:
        avail_tri_cos, avail_loop_sel_status, avail_loop_inds = self._container.get_loop_selection_available(
            add_rem_status)
        avail_cos += avail_tri_cos
        avail_sel_status += avail_loop_sel_status
        avail_inds += avail_loop_inds

    face_switch_pont = len(avail_inds)
    avail_cos += [f.calc_center_median() for f in self._object_bm.faces]
    if add_rem_status == 2:
        avail_sel_status += [True for i in self._object_bm.faces]
    else:
        avail_sel_status += [False for i in self._object_bm.faces]
    avail_inds += [i.index for i in self._object_bm.faces]

    change, unselect, new_active, new_sel_add, new_sel_remove = lasso_points_selection_test(
        self._mode_cache[0], avail_cos, avail_sel_status, self._mouse_reg_loc, self.act_reg, self.act_rv3d, add_rem_status, self._x_ray_mode, self._object_bvh)

    if change:
        if unselect:
            for po in self._container.points:
                po.set_select(False)

        for i, ind in enumerate(new_sel_add + new_sel_remove):
            status = True
            if i >= len(new_sel_add):
                status = False

            po_ind = avail_inds[ind]
            if ind < loop_switch_pont:
                self._container.points[po_ind].set_select(status)
            elif ind >= face_switch_pont:
                if self._individual_loops:
                    self._container.set_face_loops_select(
                        po_ind, status)
                else:
                    self._container.set_face_verts_select(
                        po_ind, status)
            else:
                self._container.points[po_ind[0]
                                       ].loops[po_ind[1]].set_select(status)
                self._container.points[po_ind[0]
                                       ].set_selection_from_loops()

        if self._active_point != None:
            if self._active_point.select == False:
                self._container.clear_active()
                self._active_point = None

    return change


##
##
##
##
##


#
# ORBIT EMPTY
#
def add_orbit_empty(ob):
    for i in range(len(bpy.context.selected_objects)):
        bpy.context.selected_objects[0].select_set(False)

    emp = bpy.data.objects.new('ABN_Orbit Empty', None)
    emp.empty_display_size = 0.0
    emp.matrix_world = ob.matrix_world.copy()
    bpy.context.collection.objects.link(emp)
    bpy.context.view_layer.objects.active = emp
    return emp


def update_orbit_empty(self):
    # Reset selection to only orbit object
    for i in range(len(bpy.context.selected_objects)):
        bpy.context.selected_objects[0].select_set(False)

    self._orbit_ob.select_set(True)
    bpy.context.view_layer.objects.active = self._orbit_ob

    sel_cos = self._container.get_selected_loop_cos()
    avg_loc = average_vecs(sel_cos)

    if avg_loc != None:
        gizmo_update_hide(self, True)
        self._orbit_ob.matrix_world.translation = avg_loc
    else:
        gizmo_update_hide(self, False)
        self._orbit_ob.matrix_world.translation = self._object.location

    self._orbit_ob.select_set(True)
    bpy.context.view_layer.objects.active = self._orbit_ob

    if self._use_gizmo:
        self._window.update_gizmo_pos(self._orbit_ob.matrix_world)
        relocate_gizmo_panel(self)

    return


def delete_orbit_empty(self):
    if self._orbit_ob != None:
        try:
            bpy.data.objects.remove(self._orbit_ob)
        except:
            self._orbit_ob = None

    return


#
# KEYMAP TEST/LOAD
#
def load_keymap(self):
    # self.keymap = {}

    # for item in addon_keymaps[0][0].keymap_items:
    #     self.keymap[item.name] = item

    self.keymap = addon_keymaps[0]
    return


def keys_find(keymap_items, event):
    scroll_up = ['WHEELINMOUSE', 'WHEELUPMOUSE']
    scroll_down = ['WHEELOUTMOUSE', 'WHEELDOWNMOUSE']

    key_val = []
    for key in keymap_items:
        if key.type == event.type or (key.type in scroll_up and event.type in scroll_up) or (key.type in scroll_down and event.type in scroll_down):
            if (key.alt == event.alt and key.ctrl == event.ctrl and key.shift == event.shift) or key.any:
                if key.value == event.value:
                    key_val.append(key.name)

    # if len(key_val) == 0:
    #     key_val = None
    return key_val


def test_navigation_key(nav_list, event):
    nav_status = False

    scroll_up = ['WHEELINMOUSE', 'WHEELUPMOUSE']
    scroll_down = ['WHEELOUTMOUSE', 'WHEELDOWNMOUSE']

    nav_inds = [i for i in range(
        len(nav_list)) if (nav_list[i][0] == event.type and nav_list[i][1] == event.value) or (nav_list[i][0] in scroll_up and event.type in scroll_up) or (nav_list[i][0] in scroll_down and event.type in scroll_down)]
    if len(nav_inds) > 0:
        for ind in nav_inds:
            nav_key = nav_list[ind]
            if nav_key[2] or (event.ctrl == nav_key[3] and event.shift == nav_key[4] and event.alt == nav_key[5]):
                nav_status = True

    return nav_status
