"""Copyright (c) 2010-2012 David Rio Vierra

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE."""
import atexit
import shutil
import tempfile

from OpenGL.GL import *
from editortools.thumbview import ThumbView, BlockThumbView
from operation import Operation
from pymclevel import *
import pymclevel

from albow import *
from albow.openglwidgets import GLPerspective
import numpy
from numpy import *

from pygame import key
from pygame.locals import *

from mceutils import *
import mcplatform
from depths import DepthOffset
from renderer import *
import bresenham
import config
import operator
import pymclevel
from glutils import *
from OpenGL.GL.images import glTexImage2D
from glbackground import *
from albow.dialogs import Dialog
from pymclevel.mclevelbase import exhaust
from albow.root import Cancel
from pymclevel.box import Vector



class ToolOptions(Panel):
    @property
    def editor(self):
        return self.tool.editor


class BlockView(GLOrtho):
    def __init__(self, materials, blockInfo=None):
        GLOrtho.__init__(self)
        self.list = DisplayList(self._gl_draw)
        self.blockInfo = blockInfo or materials.Air
        self.materials = materials

    listBlockInfo = None

    def gl_draw(self):
        if self.listBlockInfo != self.blockInfo:
            self.list.invalidate()
            self.listBlockInfo = self.blockInfo

        self.list.call()

    def _gl_draw(self):
        blockInfo = self.blockInfo
        if blockInfo.ID is 0:
            return

        glColor(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_ALPHA_TEST)
        self.materials.terrainTexture.bind()
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glVertexPointer(2, GL_FLOAT, 0, array([-1, -1,
                                 - 1, 1,
                                 1, 1,
                                 1, -1, ], dtype='float32'))
        texOrigin = self.materials.blockTextures[blockInfo.ID, blockInfo.blockData, 0]

        glTexCoordPointer(2, GL_FLOAT, 0, array([texOrigin[0], texOrigin[1] + 16,
                                  texOrigin[0], texOrigin[1],
                                  texOrigin[0] + 16, texOrigin[1],
                                  texOrigin[0] + 16, texOrigin[1] + 16], dtype='float32'))

        glDrawArrays(GL_QUADS, 0, 4)

        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisable(GL_ALPHA_TEST)
        glDisable(GL_TEXTURE_2D)

    @property
    def tooltipText(self):
        return "{0}".format(self.blockInfo.name)


class BlockButton(ButtonBase, Panel):
    _ref = None

    def __init__(self, materials, blockInfo=None, ref=None, recentBlocks=None, *a, **kw):
        self.allowWildcards = False
        Panel.__init__(self, *a, **kw)

        self.bg_color = (1, 1, 1, 0.25)
        self._ref = ref
        if blockInfo is None and ref is not None:
            blockInfo = ref.get()
        blockInfo = blockInfo or materials.Air

        if recentBlocks is not None:
            self.recentBlocks = recentBlocks
        else:
            self.recentBlocks = []

        self.blockView = BlockThumbView(materials, blockInfo, size=(48, 48))
        self.blockLabel = ValueDisplay(ref=AttrRef(self, 'labelText'), width=180, align="l")
        row = Row((self.blockView, self.blockLabel), align="b")

        # col = Column( (self.blockButton, self.blockNameLabel) )
        self.add(row)
        self.shrink_wrap()

        # self.blockLabel.bottom = self.blockButton.bottom
        # self.blockLabel.centerx = self.blockButton.centerx

        # self.add(self.blockLabel)

        self.materials = materials
        self.blockInfo = blockInfo
        # self._ref = ref
        self.updateRecentBlockView()

    recentBlockLimit = 7

    @property
    def blockInfo(self):
        if self._ref:
            return self._ref.get()
        else:
            return self._blockInfo

    @blockInfo.setter
    def blockInfo(self, bi):
        if self._ref:
            self._ref.set(bi)
        else:
            self._blockInfo = bi
        self.blockView.blockInfo = bi
        if bi not in self.recentBlocks:
            self.recentBlocks.append(bi)
            if len(self.recentBlocks) > self.recentBlockLimit:
                self.recentBlocks.pop(0)
            self.updateRecentBlockView()

    @property
    def labelText(self):
        labelText = self.blockInfo.name
        if len(labelText) > 24:
            labelText = labelText[:23] + "..."
        return labelText

        # self.blockNameLabel.text =

    def createRecentBlockView(self):
        def makeBlockView(bi):
            bv = BlockView(self.materials, bi)
            bv.size = (16, 16)

            def action(evt):
                self.blockInfo = bi
            bv.mouse_up = action
            return bv

        row = [makeBlockView(bi) for bi in self.recentBlocks]
        row = Row(row)

        widget = GLBackground()
        widget.bg_color = (0.8, 0.8, 0.8, 0.8)
        widget.add(row)
        widget.shrink_wrap()
        widget.anchor = "whtr"
        return widget

    def updateRecentBlockView(self):
        if self.recentBlockView:
            self.recentBlockView.set_parent(None)
        self.recentBlockView = self.createRecentBlockView()

        self.recentBlockView.right = self.width
        self.add(self.recentBlockView)
        #print self.rect, self.recentBlockView.rect

    recentBlockView = None

    @property
    def tooltipText(self):
        return "{0}".format(self.blockInfo.name)

    def action(self):
        blockPicker = BlockPicker(self.blockInfo, self.materials, allowWildcards=self.allowWildcards)
        if blockPicker.present():
            self.blockInfo = blockPicker.blockInfo


def anySubtype(self):
    bl = materials.Block(self.materials, self.ID, self.blockData)
    bl.wildcard = True
    return bl

from pymclevel.materials import Block

Block.anySubtype = anySubtype
Block.wildcard = False  # True if


class BlockPicker(Dialog):
    is_gl_container = True

    def __init__(self, blockInfo, materials, *a, **kw):
        self.allowWildcards = False
        Dialog.__init__(self, *a, **kw)
        panelWidth = 350

        self.materials = materials
        self.anySubtype = blockInfo.wildcard

        self.matchingBlocks = materials.allBlocks

        try:
            self.selectedBlockIndex = self.matchingBlocks.index(blockInfo)
        except ValueError:
            self.selectedBlockIndex = 0
            for i, b in enumerate(self.matchingBlocks):
                if blockInfo.ID == b.ID and blockInfo.blockData == b.blockData:
                    self.selectedBlockIndex = i
                    break

        lbl = Label("Search")
        # lbl.rect.topleft = (0,0)

        fld = TextField(300)
        # fld.rect.topleft = (100, 10)
        # fld.centery = lbl.centery
        # fld.left = lbl.right

        fld.change_action = self.textEntered
        fld.enter_action = self.ok
        fld.escape_action = self.cancel

        self.awesomeField = fld

        searchRow = Row((lbl, fld))

        def formatBlockName(x):
            block = self.matchingBlocks[x]
            r = "({id}:{data}) {name}".format(name=block.name, id=block.ID, data=block.blockData)
            if block.aka:
                r += " [{0}]".format(block.aka)

            return r

        tableview = TableView(columns=[TableColumn(" ", 24, "l", lambda x: ""), TableColumn("(ID) Name [Aliases]", 276, "l", formatBlockName)])
        tableicons = [BlockView(materials) for i in range(tableview.rows.num_rows())]
        for t in tableicons:
            t.size = (16, 16)
            t.margin = 0
        icons = Column(tableicons, spacing=2)

        # tableview.margin = 5
        tableview.num_rows = lambda: len(self.matchingBlocks)
        tableview.row_data = lambda x: (self.matchingBlocks[x], x, x)
        tableview.row_is_selected = lambda x: x == self.selectedBlockIndex
        tableview.click_row = self.selectTableRow
        draw_table_cell = tableview.draw_table_cell

        def draw_block_table_cell(surf, i, data, cell_rect, column):
            if isinstance(data, Block):

                tableicons[i - tableview.rows.scroll].blockInfo = data
            else:
                draw_table_cell(surf, i, data, cell_rect, column)

        tableview.draw_table_cell = draw_block_table_cell
        tableview.width = panelWidth
        tableview.anchor = "lrbt"
        # self.add(tableview)
        self.tableview = tableview
        tableWidget = Widget()
        tableWidget.add(tableview)
        tableWidget.shrink_wrap()

        def wdraw(*args):
            for t in tableicons:
                t.blockInfo = materials.Air

        tableWidget.draw = wdraw
        self.blockButton = blockView = BlockThumbView(materials, self.blockInfo)

        blockView.centerx = self.centerx
        blockView.top = tableview.bottom

        # self.add(blockview)

        but = Button("OK")
        but.action = self.ok
        but.top = blockView.bottom
        but.centerx = self.centerx
        but.align = "c"
        but.height = 30

        if self.allowWildcards:
        # self.add(but)
            anyRow = CheckBoxLabel("Any Subtype", ref=AttrRef(self, 'anySubtype'), tooltipText="Replace blocks with any data value. Only useful for Replace operations.")
            col = Column((searchRow, tableWidget, anyRow, blockView, but))
        else:
            col = Column((searchRow, tableWidget, blockView, but))
        col.anchor = "wh"
        self.anchor = "wh"

        panel = GLBackground()
        panel.bg_color = [i / 255. for i in self.bg_color]
        panel.anchor = "tlbr"
        self.add(panel)

        self.add(col)
        self.add(icons)
        icons.topleft = tableWidget.topleft
        icons.top += tableWidget.margin + 30
        icons.left += tableWidget.margin + 4

        self.shrink_wrap()
        panel.size = self.size

        try:
            self.tableview.rows.scroll_to_item(self.selectedBlockIndex)
        except:
            pass

    @property
    def blockInfo(self):
        if len(self.matchingBlocks):
            bl = self.matchingBlocks[self.selectedBlockIndex]
            if self.anySubtype:
                return bl.anySubtype()
            else:
                return bl

        else:
            return self.materials.Air

    def selectTableRow(self, i, e):
        oldIndex = self.selectedBlockIndex

        self.selectedBlockIndex = i
        self.blockButton.blockInfo = self.blockInfo
        if e.num_clicks > 1 and oldIndex == i:
            self.ok()

    def textEntered(self):
        text = self.awesomeField.text
        blockData = 0
        try:
            if ":" in text:
                text, num = text.split(":", 1)
                blockData = int(num) & 0xf
                blockID = int(text) & 0xff
            else:
                blockID = int(text) & 0xff

            block = self.materials.blockWithID(blockID, blockData)

            self.matchingBlocks = [block]
            self.selectedBlockIndex = 0
            self.tableview.rows.scroll_to_item(self.selectedBlockIndex)
            self.blockButton.blockInfo = self.blockInfo

            return
        except ValueError:
            pass
        except Exception, e:
            print repr(e)

        blocks = self.materials.allBlocks

        matches = blocks
        oldBlock = self.materials.Air
        if len(self.matchingBlocks):
            oldBlock = self.matchingBlocks[self.selectedBlockIndex]

        if len(text):
            matches = self.materials.blocksMatching(text)
            if blockData:
                ids = set(b.ID for b in matches)
                matches = sorted([self.materials.blockWithID(id, blockData) for id in ids])

            self.matchingBlocks = matches
        else:
            self.matchingBlocks = blocks

        if oldBlock in self.matchingBlocks:
            self.selectedBlockIndex = self.matchingBlocks.index(oldBlock)
        else:
            self.selectedBlockIndex = 0

        self.tableview.rows.scroll_to_item(self.selectedBlockIndex)
        self.blockButton.blockInfo = self.blockInfo


class EditorTool(object):
    surfaceBuild = False
    panel = None
    optionsPanel = None
    toolIconName = None
    worldTooltipText = None
    previewRenderer = None

    tooltipText = "???"

    def levelChanged(self):
        """ called after a level change """
        pass

    @property
    def statusText(self):
        return ""

    @property
    def cameraDistance(self):
        return self.editor.cameraToolDistance

    def toolEnabled(self):
        return True

    def __init__(self, editor):
        self.editor = editor

    def toolReselected(self):
        pass

    def toolSelected(self):
        pass

    def drawTerrainReticle(self):
        pass

    def drawTerrainMarkers(self):
        pass

    def drawTerrainPreview(self, origin):
        if self.previewRenderer is None:
            return
        self.previewRenderer.origin = map(lambda a, b: a - b, origin, self.level.bounds.origin)

        glPolygonOffset(DepthOffset.ClonePreview, DepthOffset.ClonePreview)
        glEnable(GL_POLYGON_OFFSET_FILL)
        self.previewRenderer.draw()
        glDisable(GL_POLYGON_OFFSET_FILL)

    def rotate(self, amount=1):
        pass

    def roll(self, amount=1):
        pass

    def flip(self, amount=1):
        pass

    def mirror(self, amount=1):
        pass

    def swap(self, amount=1):
        pass

    def mouseDown(self, evt, pos, direction):
        '''pos is the coordinates of the block under the cursor,
        direction indicates which face is under it.  the tool performs
        its action on the specified block'''

        pass

    def mouseUp(self, evt, pos, direction):
        pass

    def mouseDrag(self, evt, pos, direction):
        pass

    def increaseToolReach(self):
        "Return True if the tool handles its own reach"
        return False

    def decreaseToolReach(self):
        "Return True if the tool handles its own reach"
        return False

    def resetToolReach(self):
        "Return True if the tool handles its own reach"
        return False

    def confirm(self):
        ''' called when user presses enter '''
        pass

    def cancel(self):
        '''cancel the current operation.  called when a different tool
        is picked, escape is pressed, or etc etc'''
        self.hidePanel()

    #        pass

    def findBestTrackingPlane(self, face):
        cv = list(self.editor.mainViewport.cameraVector)
        cv[face >> 1] = 0
        cv = map(abs, cv)

        return cv.index(max(cv))

    def drawToolReticle(self):

        '''get self.editor.blockFaceUnderCursor for pos and direction.
        pos is the coordinates of the block under the cursor,
        direction indicates which face is under it. draw something to
        let the user know where the tool is going to act.  e.g. a
        transparent block for the block placing tool.'''

        pass

    def drawToolMarkers(self):
        ''' draw any markers the tool wants to leave in the field
        while another tool is out.  e.g. the current selection for
        SelectionTool'''

        pass

    def selectionChanged(self):
        """ called when the selection changes due to nudge. other tools can be active. """
        pass

    edge_factor = 0.1

    def boxFaceUnderCursor(self, box):
        if self.editor.mainViewport.mouseMovesCamera:
            return None, None

        p0 = self.editor.mainViewport.cameraPosition
        normal = self.editor.mainViewport.mouseVector
        if normal is None:
            return None, None

        points = {}

#        glPointSize(5.0)
#        glColor(1.0, 1.0, 0.0, 1.0)
#        glBegin(GL_POINTS)

        for dim in range(3):
            dim1 = dim + 1
            dim2 = dim + 2
            dim1 %= 3
            dim2 %= 3

            def pointInBounds(point, x):
                return box.origin[x] <= point[x] <= box.maximum[x]

            neg = normal[dim] < 0

            for side in 0, 1:

                d = (box.maximum, box.origin)[side][dim] - p0[dim]

                if d >= 0 or (neg and d <= 0):
                    if normal[dim]:
                        scale = d / normal[dim]

                        point = map(lambda a, p: (a * scale + p), normal, p0)
    #                    glVertex3f(*point)

                        if pointInBounds(point, dim1) and pointInBounds(point, dim2):
                            points[dim * 2 + side] = point

#        glEnd()

        if not len(points):
            return None, None

        cp = self.editor.mainViewport.cameraPosition
        distances = dict((sum(map(lambda a, b: (b - a) ** 2, cp, point)), (face, point)) for face, point in points.iteritems())
        if not len(distances):
            return None, None

        # When holding alt, pick the face opposite the camera
        # if key.get_mods() & KMOD_ALT:
        #    minmax = max
        # else:

        face, point = distances[min(distances.iterkeys())]

        # if the point is near the edge of the face, and the edge is facing away,
        # return the away-facing face

        dim = face // 2
        side = face & 1

        dim1, dim2 = dim + 1, dim + 2
        dim1, dim2 = dim1 % 3, dim2 % 3
        cv = self.editor.mainViewport.cameraVector

        # determine if a click was within self.edge_factor of the edge of a selection box side. if so, click through
        # to the opposite side
        for d in dim1, dim2:
            edge_width = box.size[d] * self.edge_factor
            facenormal = [0, 0, 0]
            cameraBehind = False

            if point[d] - box.origin[d] < edge_width:
                facenormal[d] = -1
                cameraBehind = cp[d] - box.origin[d] > 0
            if point[d] - box.maximum[d] > -edge_width:
                facenormal[d] = 1
                cameraBehind = cp[d] - box.maximum[d] < 0

            if dot(facenormal, cv) > 0 or cameraBehind:
                # the face adjacent to the clicked edge faces away from the cam
                return distances[max(distances.iterkeys())]

        return face, point

    def selectionCorners(self):
        """ returns the positions of the two selection corners as a pair of 3-tuples, each ordered x,y,z """

        if(None != self.editor.selectionTool.bottomLeftPoint and
           None != self.editor.selectionTool.topRightPoint):

            return (self.editor.selectionTool.bottomLeftPoint,
                    self.editor.selectionTool.topRightPoint)

        return None

    def selectionBoxForCorners(self, p1, p2):
        ''' considers p1,p2 as the marked corners of a selection.
        returns a BoundingBox containing all the blocks within.'''

        if self.editor.level is None:
            return None

        p1, p2 = list(p1), list(p2)
        # d = [(a-b) for a,b in zip(p1,p2)]
        for i in range(3):
            if p1[i] > p2[i]:
                t = p2[i]
                p2[i] = p1[i]
                p1[i] = t

            p2[i] += 1

        size = map(lambda a, b: a - b, p2, p1)

        if p1[1] < 0:
            size[1] += p1[1]
            p1[1] = 0

        h = self.editor.level.Height
        if p1[1] >= h:
            p1[1] = h - 1
            size[1] = 1

        if p1[1] + size[1] >= h:
            size[1] = h - p1[1]

        return BoundingBox(p1, size)

    def selectionBox(self):
        ''' selection corners, ordered, with the greater point moved up one block for use as the ending value of an array slice '''
        c = self.selectionCorners()
        if c:
            return self.selectionBoxForCorners(*c)

        return None

    def selectionSize(self):
        ''' returns a tuple containing the size of the selection (x,y,z)'''
        c = self.selectionBox()
        if c is None:
            return None
        return c.size

    @property
    def maxBlocks(self):
        from leveleditor import Settings
        return Settings.blockBuffer.get() / 2  # assume block buffer in bytes

    def showPanel(self):
        pass

    def hidePanel(self):
        if self.panel and self.panel.parent:
            self.panel.parent.remove(self.panel)
            self.panel = None

    def performWithRetry(self, op, recordUndo=True):
        try:
            op.perform(recordUndo)
        except MemoryError:
            self.editor.invalidateAllChunks()
            op.perform(recordUndo)


Operation.maxBlocks = EditorTool.maxBlocks
