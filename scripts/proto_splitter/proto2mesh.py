#!/usr/bin/env python3

# Copyright 1996-2020 Cyberbotics Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author Simon Steinmann (https://github.com/Simon-Steinmann)
#


# Automatic PROTO to multi-file PROTO trimesh extractor
#
# INSTRUCTIONS:
# Call the script with the --input=<path> argument
#
# 1. if <path> ends in <filename.proto>:
#   - creates a new folder in the same directory named "multifile_<filename>"
#   - creates a new <filename.proto> inside this folder with all trimeshes
#     replaced by proto files, placed in a subfolder.
#   - the mesh proto files in the subfolder have the same header as the
#     original file, with the additional 'hidden' tag added.
#
# 2. If <path> does not end in ".proto" -> assumes directory
#   - duplicates our chosen <path> and appends "_multiProto_0" to the name
#   - the original <path> remains unchanged. If executed multiple times, the
#     trailing number for the <path> duplicates increases.
#   - searches for every .proto file in the duplicated <path> recursively and:
#       - ignores .proto file with either no header or a 'hidden' tag
#       - replaces the file with a version, where meshes are extracted and put
#         into a "<filename>_meshes" folder.
#       - the mesh proto files in the subfolder have the same header as the
#         original file, with the additional 'hidden' tag added.
#
#


import os
import optparse
import shutil
import numpy as np
import trimesh


class proto2multi:
    def __init__(self):
        print("Proto 2 multi-file proto converter by Simon Steinmann")

    def get_data_from_field(self, ln):
        i = ln.index('[')
        data = ' '.join(ln[i:])
        while ']' not in ln:
            line = self.f.readline()
            ln = line.split()
            data += line
        data = ' '.join(data.split())
        data = data.replace("[", '').replace("]", '')
        return ln, data

    def convert(self, inFile, outFile=None):
        path = os.path.dirname(inFile)
        self.robotName = os.path.splitext(os.path.basename(inFile))[0]
        if outFile is None:
            newPath = "{}/{}_multifile".format(path, self.robotName)
            outFile = "{}/{}.proto".format(newPath, self.robotName)
        else:
            newPath = os.path.dirname(outFile)
        os.makedirs(newPath, exist_ok=True)
        # make a dir called 'x_meshes'
        os.makedirs(outFile.replace(".proto", "") + "_meshes", exist_ok=True)
        self.meshFilesPath = outFile.replace(".proto", "") + "_meshes"
        self.f = open(inFile)
        self.protoFileString = ""
        self.pf = open(outFile, "w")
        self.shapeIndex = 0
        parentDefName = None
        meshData = {}
        meshID = 0
        indent = "  "
        level = 0
        while True:
            line = self.f.readline()
            ln = line.split()
            # termination condition:
            eof = 0
            while ln == []:
                self.protoFileString += line
                line = self.f.readline()
                ln = line.split()
                eof += 1
                if eof > 10:
                    self.f.close()
                    self.cleanup(inFile)
                    self.writeOBJ(meshData)
                    self.pf.write(self.protoFileString)
                    self.pf.close()
                    return
            if "name" in ln:
                name = ln[ln.index("name") + 1].replace('"', "")
                if name == "IS":
                    name = "base_link"
                counter = 0
                for k, v in meshData.items():
                    if v[-1] is None:
                        mlvl = int(k.split('_')[0])
                        if mlvl in [level + 2, level + 4]:
                            v[-1] = name + "_" + str(counter)
                            counter += 1
            if "DEF" in ln:
                if "Group" in ln or "Transform" in ln or "Shape" in ln:
                    parentDefName = str(level) + "_" + ln[ln.index("DEF") + 1]
            if "IndexedFaceSet" in ln:
                coord = coordIndex = texCoord = texCoordIndex = normal = normalIndex = creaseAngle = name = None
                defString = ""
                if "DEF" in ln:
                    defString = "DEF " + ln[ln.index("DEF") + 1]
                    name = ln[ln.index("DEF") + 1]
                if parentDefName is not None:
                    name = parentDefName.split("_")[1]
                shapeLevel = 1
                meshID += 1
                while shapeLevel > 0:
                    if 'coord' in ln:
                        line = self.f.readline()
                        ln = line.split()
                        ln, coord = self.get_data_from_field(ln)
                    if 'texCoord' in ln:
                        line = self.f.readline()
                        ln = line.split()
                        ln, texCoord = self.get_data_from_field(ln)
                    if 'normal' in ln:
                        line = self.f.readline()
                        ln = line.split()
                        ln, normal = self.get_data_from_field(ln)
                    if 'coordIndex' in ln:
                        ln, coordIndex = self.get_data_from_field(ln)
                    if 'texCoordIndex' in ln:
                        ln, texCoordIndex = self.get_data_from_field(ln)
                    if 'normalIndex' in ln:
                        ln, normalIndex = self.get_data_from_field(ln)
                    if 'creaseAngle' in ln:
                        creaseAngle = ln[ln.index("creaseAngle") + 1]
                    line = self.f.readline()
                    ln = line.split()
                    if "}" in ln:
                        shapeLevel -= 1
                    if "{" in ln:
                        shapeLevel += 1
                key = str(level) + '_' + str(meshID)
                meshData[key] = [coord, coordIndex, texCoord, texCoordIndex, normal, normalIndex, creaseAngle, name]
                parentDefName = None
                self.protoFileString += indent * level + "geometry " + defString + ' Mesh {\n'
                self.protoFileString += indent * (level + 1) + "url MeshID_" + key + '_placeholder\n'
                self.protoFileString += indent * level + "}\n"
            else:
                if "}" in ln or "]" in ln:
                    level -= 1
                    if parentDefName is not None:
                        if level < int(parentDefName.split("_")[0]):
                            parentDefName = None
                elif "{" in ln or "[" in ln:
                    level += 1
                self.protoFileString += line

    def cleanup(self, inFile, outFile=None):
        if inFile.endswith("_temp"):
            os.remove(inFile)
        if outFile is not None:
            os.remove(outFile)

    def convert_all(self, sourcePath):
        outPath = self.create_multiProtoDir(sourcePath)
        os.makedirs(outPath, exist_ok=True)
        # Find all the proto files, and store their filePaths
        os.chdir(sourcePath)
        # Walk the tree.
        protoFiles = []  # List of the full filepaths.
        for root, directories, files in os.walk("./"):
            for filename in files:
                # Join the two strings in order to form the full filepath.
                if filename.endswith(".proto"):
                    filepath = os.path.join(root, filename)
                    filepath = filepath[1:]
                    protoFiles.append(filepath)
        for proto in protoFiles:
            inFile = sourcePath + proto
            outFile = outPath + proto
            print("converting " + outFile)
            # make a copy of our inFile, which will be read and later deleted
            shutil.copy(inFile, inFile + "_temp")
            inFile = inFile + "_temp"
            self.convert(inFile, outFile)

    def create_multiProtoDir(self, sourcePath):
        # Create a backup of the folder we are converting
        newDirName = os.path.basename(sourcePath) + "_multiProto_0"
        newDirPath = os.path.dirname(sourcePath) + "/" + newDirName
        n = 0
        while os.path.isdir(newDirPath):
            n += 1
            newDirPath = newDirPath[:-1] + str(n)
        shutil.copytree(sourcePath, newDirPath)
        return newDirPath

    def writeOBJ(self, meshData):
        counter = 0
        for k, v in meshData.items():
            # print(np.array(v[1].split(','), dtype=int))
            name = v[-1] if v[-1] is not None else "base_link" + str(counter)
            # Replace the placholder ID of the generated .obj meshes with their path
            searchString = "MeshID_" + k + "_placeholder"
            replaceString = '"' + self.robotName + '_meshes/' + name + '.obj"'
            self.protoFileString = self.protoFileString.replace(searchString, replaceString)
            # Create a new .obj mesh file
            filepath = "{}/{}.obj".format(self.meshFilesPath, name)
            filepath2 = "{}/{}_SMOOTH.obj".format(self.meshFilesPath, name)
            f = open(filepath, "w")
            f.write("o " + name + '\n')
            # vertices
            verticies = np.array(v[0].replace(',', '').split(), dtype=float).reshape(-1, 3)
            print(name)
            vertexIndex = v[1].replace(',', '').split('-1')
            for vertex in verticies:
                f.write('v {} {} {}\n'.format(vertex[0], vertex[1], vertex[2]))
            faceType = "v"
            # texture coordinates
            if v[2] is not None:
                texCoords = np.array(v[2].replace(',', '').split(), dtype=float).reshape(-1, 2)
                texIndex = v[3].replace(',', '').split('-1')
                for vt in texCoords:
                    f.write('vt {} {}\n'.format(vt[0], vt[1]))
                faceType += "t"
            # normal coordinates
            if v[4] is not None:
                normals = np.array(v[4].replace(',', '').split(), dtype=float).reshape(-1, 3)
                normalIndex = v[5].replace(',', '').split('-1')
                for vn in normals:
                    f.write('vn {} {} {}\n'.format(vn[0], vn[1], vn[2]))
                faceType += "n"

            # faces
            for n in range(len(vertexIndex)):
                vIndices = np.array(vertexIndex[n].split(), dtype=int)
                size = len(vIndices)
                v_i = vIndices + [1] * size
                if v[2] is not None:
                    tIndices = np.array(texIndex[n].split(), dtype=int)
                    t_i = tIndices + [1] * size
                if v[4] is not None:
                    nIndices = np.array(normalIndex[n].split(), dtype=int)
                    n_i = nIndices + [1] * size

                # if size < 3:
                #    break
                f.write('f')
                for i in range(size):
                    if faceType == "v":
                        f.write(' {}'.format(v_i[i]))
                    if faceType == "vt":
                        f.write(' {}/{}'.format(v_i[i], t_i[i]))
                    if faceType == "vn":
                        f.write(' {}//{}'.format(v_i[i], n_i[i]))
                    if faceType == "vtn":
                        f.write(' {}/{}/{}'.format(v_i[i], t_i[i], n_i[i]))
                f.write('\n')
            counter += 1
            f.close()
            mesh = trimesh.exchange.load.load(filepath)

            mesh = mesh.process(validate=False)
            mesh.remove_unreferenced_vertices()
            mesh.remove_duplicate_faces()
            mesh = mesh.smoothed(angle=float(v[-2]))
            print('creaseAngle: ' + v[-2])
            mesh.vertex_normals = mesh.vertex_normals
            # print(mesh.visual)

            exportStr = trimesh.exchange.obj.export_obj(mesh)
            # for i in range(5):
            #     exportStr = exportStr.replace('0 ', ' ')#.replace('0\n', '\n')
            f = open(filepath2, "w")
            f.write(exportStr)
            f.close
            # trimesh.exchange.export.export_mesh(mesh, filepath2)


if __name__ == "__main__":
    optParser = optparse.OptionParser(usage="usage: %prog  [options]")
    optParser.add_option(
        "--input",
        dest="inPath",
        default=None,
        help="Specifies the proto file, or a directory. Converts all .proto files, if it is a directory.",
    )
    options, args = optParser.parse_args()
    inPath = options.inPath
    if inPath is not None:
        p2m = proto2multi()
        if os.path.splitext(inPath)[1] == ".proto":
            p2m.convert(inPath)
            print("Multi-file extraction done")
        elif os.path.isdir(inPath):
            inPath = os.path.abspath(inPath)
            p2m.convert_all(inPath)
            print("Multi-file extraction done")
        else:
            print("ERROR: --input has to be a .proto file or directory!")
    else:
        print(
            "Mandatory argument --input=<path> missing!\nSpecify a .proto file or directory path."
        )
