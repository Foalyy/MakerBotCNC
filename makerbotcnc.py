#!/usr/bin/env python2

import os, sys, readline, json, re, math
import pygame
import Makerbot, getch

# Project infos
project = {
    "name" : "",
    "layersOrder": [],
    "layers": {}
}

# List of available commands
commands = [
    "help",
    "new",
    "add",
    "layers",
    "layer",
    "load",
    "plot",
    "connect",
    "run",
    "home",
    "move",
    "release",
    "exit"
]

# Commands help descriptions
commandsHelp = {
    "help" : ["", "Display this help message"],
    "new": ["", "Create a new project"],
    "add": ["", "Add a new layer"],
    "layers": ["", "Show the layers list"],
    "layer": ["", "Modify a layer"],
    "load": ["", "Load the gcode files"],
    "plot": ["", "Display the current layers"],
    "connect": ["", "Connect to the machine"],
    "run": ["", "Start manufacturing the board"],
    "home": ["", "Put the toolhead at its home position"],
    "move": ["X Y", "Move the head to the given position"],
    "release": ["", "Release the steppers, allowing the toolhead to be moved freely"],
    "exit": ["", "Exit this program"],
}

# Layers
standardLayers = [
    "F.Cu",
    "B.Cu",
    "Edge.Cuts",
    "Drill.0.6mm",
    "Drill.1mm"
]
standardLayersColors = {
    "F.Cu" : [132, 0, 0],
    "B.Cu" : [0, 132, 0],
    "Edge.Cuts" : [194, 194, 0],
    "Drill.0.6mm" : [0, 0, 160],
    "Drill.1mm" : [0, 100, 200]
}

# Machine orders generated from gcode
orders = {}

# Tools
standardTools = [
    {"diameter" : 0.2, "description" : "0.2mm engraving bit"},
    {"diameter" : 1.8, "description" : "1.8mm milling bit"},
    {"diameter" : 0.6, "description" : "0.6mm drilling bit"},
    {"diameter" : 1, "description" : "1mm drilling bit"}
]
standardLayersTools = {
    "F.Cu" : 0,
    "B.Cu" : 0,
    "Edge.Cuts" : 1,
    "Drill.0.6mm" : 2,
    "Drill.1mm" : 3
}


# Setup prompt
readline.parse_and_bind("tab: complete")
def complete(text, state):
    results = [x + " " for x in commands if x.startswith(text)] + [None]
    return results[state]
readline.set_completer(complete)

# Create machine driver
mb = Makerbot.Makerbot()

# Method used to get a pressed key
getch = getch._Getch()


## Interactively ask the user for something
def ask(prompt="", choices=None, default=None, type=str):
    while True:
        completer = readline.get_completer()
        readline.set_completer(None)
        try:
            answer = raw_input(prompt).lower()
        except (EOFError, KeyboardInterrupt):
            cmd_exit()
        readline.set_completer(completer)
        if answer == "":
            if default != None:
                return default
        else:
            if type == int:
                answer = int(answer)
            if choices == None or answer in choices:
                return answer

def waitKey():
    key = ord(getch())
    if key == 3:
        cmd_exit()


## Load a gcode file
def loadGcode(filename):
    f = file(filename, "r")
    p = re.compile(ur"(G|M|F)(\d+(?:\.\d*)?) *(X\-?\d*\.?\d*)? *(Y\-?\d*\.?\d*)? *(Z\-?\d*\.?\d*)? *(P\-?\d*\.?\d*)?", re.IGNORECASE)
    result = []
    for line in f:
        m = p.match(line)
        if m:
            g = m.groups()
            c = g[0].upper()
            n = x = y = z = None
            try:
                n = int(g[1])
            except ValueError:
                n = float(g[1])
            if g[2] != None and g[2][0].upper() == "X":
                x = float(g[2][1:])
            if g[3] != None and g[3][0].upper() == "Y":
                y = float(g[3][1:])
            if g[4] != None and g[4][0].upper() == "Z":
                z = float(g[4][1:])
            if c == "G":
                if n in [0, 1]:
                    if z:
                        result.append([z])
                    elif x and y:
                        result.append([x, y])
    return result


## Tries to load a currently existing project in the working directory
def autoLoadProject():
    global project
    ls = os.listdir(".")
    for filename in ls:
        if filename.endswith(".mbcnc"):
            f = file(filename, "r")
            project = json.load(f)
            f.close()

## Save the current project
def saveProject():
    f = file(project["name"] + ".mbcnc", "w")
    json.dump(project, f, indent=4)
    f.close()

## Command handling functions

def cmd_help(args):
    print("Available commands :")
    for command in commands:
        print(command + " " + commandsHelp[command][0])
        print("    " + commandsHelp[command][1])

def cmd_new(args):
    # Ask the user for a project name
    p = os.getcwd().split('/')
    p.reverse()
    dirname = ""
    for d in p:
        if d.lower() not in ["gcode", "gerber", "export"]:
            dirname = d
            break
    while True:
        name = ask(prompt="Project name : [" + dirname + "] ", default=dirname)
        if name == "" or name == None:
            return
        elif re.match("^[a-zA-Z0-9_]+$", name):
            break
    project["name"] = name

    # Tries to map layers automatically
    ls = os.listdir(".")
    layers = {}
    layersOrder = []
    for filename in ls:
        for layerId in standardLayers:
            if layerId.lower() in filename.lower() and not layerId in layers.keys():
                layers[layerId] = {"file" : filename, "tool" : "", "reversed" : False}
                layersOrder.append(layerId)
    if len(layers) > 0:
        print("Some layers were found :")
        for layerId in layersOrder:
            print("\t" + layerId + " : " + layers[layerId]["file"])
        mapLayers = ask(prompt="Automatically add these layers? [Y/n] ", choices=["y", "n"], default="y")
        if mapLayers == "y":
            # Ask the user to choose a tool for each layers
            print("Please select a tool to use for each layer")
            print("Available tools :")
            for i in range(len(standardTools)):
                print(str(i) + " : " + standardTools[i]["description"])
            for layerId in layersOrder:
                defaultTool = standardLayersTools[layerId]
                toolId = ask(prompt=layerId + " [" + str(defaultTool) + "] : ", choices=range(len(standardTools)), default=defaultTool, type=int)
                if toolId != -1:
                    layers[layerId]["tool"] = standardTools[toolId]
    project["layers"] = layers
    project["layersOrder"] = layersOrder
    saveProject()

def cmd_add(args):
    if project["name"] == "":
        print("Please create a project first")
        return

    if len(args) < 2 or len(args) > 3:
        print("Usage : add LAYER_NAME FILE")
        return

    layerId = args[1]
    if len(args) == 3:
        filename = args[2]
    else:
        filename = layerId + ".gcode"
    if layerId in project["layersOrder"]:
        print("Layer " + layerId + " already exists")
        return
    try:
        f = file(filename, "r")
    except IOError:
        print("No such file : " + filename)
        return
    f.close()
    print("Please select a tool to use for this layer")
    print("Available tools :")
    for i in range(len(standardTools)):
        print(str(i) + " : " + standardTools[i]["description"])
    toolId = ask(prompt=layerId + " : ", choices=range(len(standardTools)), default=-1, type=int)
    if toolId == -1:
        return
    rev = ask("Is this layer reversed? [y/N] ", choices=["y", "n"], default="n")
    rev = (rev == "y")
    project["layersOrder"].append(layerId)
    project["layers"][layerId] = {"file" : filename, "tool" : standardTools[toolId], "reversed" : rev}

def cmd_layers(args):
    if project["name"] == "":
        print("Please create a project first")
        return

    for i in range(len(project["layersOrder"])):
        layerId = project["layersOrder"][i]
        layer = project["layers"][layerId]
        rev = "[F] "
        if layer["reversed"]:
            rev = "[B] "
        print("Layer " + str(i) + " : " + rev + layerId + ", file : '" + layer["file"] + "', tool : " + layer["tool"]["description"])

def cmd_layer(args):
    if project["name"] == "":
        print("Please create a project first")
        return

    if len(args) != 3:
        print("Usage : layer LAYER_ID COMMAND")
        print("Available COMMANDs : up down reverse tool delete")
        return

    layerId = ""
    if unicode(args[1], "utf-8").isnumeric():
        i = int(args[1])
        if i >= 0 and i < len(project["layersOrder"]):
            layerId = project["layersOrder"][i]
    elif args[1] in project["layersOrder"]:
        layerId = args[1]
    if layerId == "":
        print("Unknown layer " + args[1])
        return
    layerN = -1
    for i in range(len(project["layersOrder"])):
        if project["layersOrder"][i] == layerId:
            layerN = i
            break

    command = args[2].lower()
    if command == "up":
        if layerN == 0:
            print("This layer is already on top")
        else:
            tmp = project["layersOrder"][layerN - 1]
            project["layersOrder"][layerN - 1] = project["layersOrder"][layerN]
            project["layersOrder"][layerN] = tmp
            layerN -= 1

    elif command == "down":
        if layerN == len(project["layersOrder"]) - 1:
            print("This layer is already on the bottom")
        else:
            tmp = project["layersOrder"][layerN + 1]
            project["layersOrder"][layerN + 1] = project["layersOrder"][layerN]
            project["layersOrder"][layerN] = tmp
            layerN += 1

    elif command == "reverse":
        project["layers"][layerId]["reversed"] = not project["layers"][layerId]["reversed"]

    elif command == "delete":
        a = ask("Delete layer " + layerId + "? [y/N] ", choices=["y", "n"], default="n")
        if a == "y":
            del project["layersOrder"][layerN]

    elif command == "tool":
        print("Please select a tool to use for this layer")
        print("Available tools :")
        for i in range(len(standardTools)):
            print(str(i) + " : " + standardTools[i]["description"])
        toolId = ask(prompt=layerId + " : ", choices=range(len(standardTools)), default=-1, type=int)
        if toolId > -1:
            project["layers"][layerId]["tool"] = standardTools[toolId]

    # Print the result
    cmd_layers(None)

    # Force a reload
    orders == {}

def cmd_connect(args):
    mb.autoConnect()

def cmd_home(args):
    if not mb.isConnected():
        print("Machine not connected")
        return
    print("Moving...")
    mb.home()
    mb.wait()

def cmd_release(args):
    if not mb.isConnected():
        print("Machine not connected")
        return
    mb.release()

def cmd_load(args=None):
    global orders

    if project["name"] == "":
        print("Please create a project first")
        return

    if args is not None or orders == {}:
        print("Loading Gcode files...")

        # Load gcodes
        orders = {}
        for layerId in project["layersOrder"]:
            orders[layerId] = loadGcode(project["layers"][layerId]["file"])

        # Compute bounding box
        minX = maxX = minY = maxY = 0
        for order in orders[orders.keys()[0]]:
            if len(order) == 2:
                minX = maxX = order[0]
                minY = maxY = order[1]
        for layerId in orders.keys():
            for order in orders[layerId]:
                if len(order) == 2:
                    x = order[0]
                    y = order[1]
                    if x < minX:
                        minX = x
                    elif x > maxX:
                        maxX = x
                    if y < minY:
                        minY = y
                    elif y > maxY:
                        maxY = y
        project["minX"] = minX
        project["minY"] = minY
        project["maxX"] = maxX
        project["maxY"] = maxY
        
        # Offsets to origin
        if args is not None or not "auto_offset" in project.keys():
            a = ask(prompt="Your project starts at " + str(minX) + "," + str(minY) + ". Automatically offset to origin? [Y,n] ", choices=["y", "n"], default="y")
            if a == "y":
                project["auto_offset"] = True
            else:
                project["auto_offset"] = False
        if project["auto_offset"]:
            for layerId in orders.keys():
                for order in orders[layerId]:
                    if len(order) == 2:
                        order[0] = order[0] - minX
                        order[1] = order[1] - minY
            project["minX"] = 0
            project["minY"] = 0
            project["maxX"] = maxX - minX
            project["maxY"] = maxY - minY

def cmd_plot(args):
    if project["name"] == "":
        print("Please create a project first")
        return

    if orders == {}:
        cmd_load()

    scale = 31
    margin = 5

    # Layers to plot
    layers = []
    if len(args) == 1:
        # If no layer is specified, make every layer in the project
        layers = project["layersOrder"]
    else:
        for layerId in args[1:]:
            if layerId in project["layers"].keys():
                layers.append(layerId)
            else:
                print("Unknown layer " + layerId)
                return

    # Compute bounding box
    minX = maxX = minY = maxY = 0
    for order in orders[orders.keys()[0]]:
        if len(order) == 2:
            minX = maxX = order[0]
            minY = maxY = order[1]
    for layerId in orders.keys():
        for order in orders[layerId]:
            if len(order) == 2:
                x = order[0]
                y = order[1]
                if x < minX:
                    minX = x
                elif x > maxX:
                    maxX = x
                if y < minY:
                    minY = y
                elif y > maxY:
                    maxY = y

    # Init PyGame to display plots
    pygame.init()
    sizeX = int(math.ceil(scale * (maxX + 2 * margin)))
    sizeY = int(math.ceil(scale * (maxY + 2 * margin)))
    pygameWindowSize = [sizeX, sizeY]

    # Create the window
    pygameWindow = pygame.display.set_mode(pygameWindowSize, pygame.RESIZABLE)

    # Wait for a window event
    redraw = True
    exit = False
    viewPos = [0, 0]
    while not exit:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.display.quit()
                exit = True

            elif event.type == pygame.VIDEORESIZE:
                pygameWindowSize = event.size
                pygameWindow = pygame.display.set_mode(pygameWindowSize, pygame.RESIZABLE)
                redraw = True

            elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
                viewPos = [viewPos[0] + event.rel[0], viewPos[1] + event.rel[1]]
                redraw = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 5 and scale > 20:
                    scale -= 10
                    redraw = True
                elif event.button == 4 and scale < 100:
                    scale += 10
                    redraw = True

        if redraw:
            # Fill the background
            pygameWindow.fill([255, 255, 255])

            # Plot the origin
            pygame.draw.line(pygameWindow, [0, 0, 0], [viewPos[0] + scale * margin - 20, viewPos[1] + sizeY - scale * margin], [viewPos[0] + scale * margin + 20, viewPos[1] + sizeY - scale * margin], 2)
            pygame.draw.line(pygameWindow, [0, 0, 0], [viewPos[0] + scale * margin, viewPos[1] + sizeY - (scale * margin - 20)], [viewPos[0] + scale * margin, viewPos[1] + sizeY - (scale * margin + 20)], 2)
            pygame.draw.circle(pygameWindow, [0, 0, 0], [viewPos[0] + scale * margin + 1, viewPos[1] + sizeY - (scale * margin + 1)], 10, 2)

            # Plot the layers
            for layerId in layers[::-1]:
                if layerId in standardLayersColors.keys():
                    color = standardLayersColors[layerId]
                else:
                    color = [0, 0, 0]
                lastPos = None
                size = int(round(scale * project["layers"][layerId]["tool"]["diameter"]))
                up = True
                for order in orders[layerId]:
                    if len(order) == 1:
                        if order[0] <= 0:
                            up = False
                            if lastPos is not None:
                                pygame.draw.circle(pygameWindow, color, lastPos, int(size / 2 - 1))
                        else:
                            up = True
                    elif len(order) == 2:
                        currentPos = [int(round(viewPos[0] + scale * (margin + order[0]))), int(round(viewPos[1] + sizeY - scale * (margin + order[1])))]
                        size_ = 2
                        if not up:
                            size_ = size
                        pygame.draw.circle(pygameWindow, color, currentPos, int(size_ / 2 - 1))
                        if lastPos is not None:
                            pygame.draw.line(pygameWindow, color, lastPos, currentPos, size_)
                            pygame.draw.circle(pygameWindow, color, lastPos, int(size_ / 2 - 1))
                        lastPos = currentPos
            pygame.display.flip()
            redraw = False

def cmd_move(args=[]):
    if not mb.isConnected():
        print("Machine not connected")
        return

    if len(args) == 3:
        mb.move(args[1], args[2])
    else:
        print("Keys :")
        print(" keyboard arrows : move the tool")
        print(" A/Q : raise/lower the buildplate")
        print(" +/- : increase/decrease the step")
        fifo = [0, 0, 0]
        speed = 1000
        step = 2
        steps = [0.1, 0.5, 1, 2, 5, 10]
        while True:
            sys.stdout.write("\rstep : " + str(steps[step]) + "mm, X : " + str(mb.position['x']) + "mm, Y : " + str(mb.position['y']) + "mm, Z : " + str(mb.position['z']) + "mm   ")
            mb.wait()
            key = ord(getch())
            fifo[2] = fifo[1]
            fifo[1] = fifo[0]
            fifo[0] = key
            if key in [3, 13, 22]:
                #mb.stop()
                print("")
                break
            elif fifo[2] == 27 and fifo[1] == 91:
                # Escaping sequence
                if fifo[0] == 65: # Up
                    mb.move(0, steps[step], speed=speed, relative=True)
                elif fifo[0] == 66: # Down
                    mb.move(0, -steps[step], speed=speed, relative=True)
                elif fifo[0] == 67: # Right
                    mb.move(steps[step], 0, speed=speed, relative=True)
                elif fifo[0] == 68: # Left
                    mb.move(-steps[step], 0, speed=speed, relative=True)
            elif key in [ord("a"), ord("A")]:
                mb.moveZ(steps[step], speed=speed/2, relative=True)
            elif key in [ord("q"), ord("Q")]:
                mb.moveZ(-steps[step], speed=speed/2, relative=True)
            elif key == ord("+"):
                if step < len(steps) - 1:
                    step += 1
            elif key == ord("-"):
                if step > 0:
                    step -= 1

def cmd_run(args):
    if not mb.isConnected():
        print("Machine not connected")
        return
    
    if orders == {}:
        cmd_load()

    # Layers to make
    layers = []
    if len(args) == 1:
        # If no layer is specified, make every layer in the project
        layers = project["layersOrder"]
    else:
        for layerId in args[1:]:
            if layerId in project["layers"].keys():
                layers.append(layerId)
            else:
                print("Unknown layer " + layerId)
                return

    # Home the machine
    print("Homing the machine...")
    mb.home()

    # Position offset
    offset = {'x' : 0, 'y' : 0}
    addOffset = ask("Add a position offset? [Y/n] ", choices=["y", "n"], default="y")
    if addOffset == "y":
        mb.moveZ(70)
        cmd_move()
        offset['x'] = mb.position['x']
        offset['y'] = mb.position['y']

    # Run every layer
    currentTool = None
    buildplateZ = 0
    travelHeight = 3
    reversedOriginX = 71
    wasLastReversed = None
    for layerId in layers:
        layer = project["layers"][layerId]

        print("")
        isReversed = layer["reversed"]
        rev = "FRONT"
        if isReversed:
            rev = "BACK"
        print("## Making layer " + layerId)
        skip = ask("Skip? [y/N] ", choices=["y", "n"], default="n")
        if skip == "y":
            continue

        # Tool selection
        if currentTool == layer["tool"]["description"] and wasLastReversed is not None and isReversed == wasLastReversed:
            print("This layer uses the same tool, skipping tool change and levelling")

        else:
            # Lower the buildplate
            mb.moveZ(0)

            # Board side
            if wasLastReversed is None:
                print("This layer is on the " + rev + " side")
                waitKey()
            elif isReversed != wasLastReversed:
                print("Please turn the board to the " + rev + " side")
                waitKey()

            # Move to the center
            mb.wait()
            mb.move(reversedOriginX / 2, 10)

            if currentTool != layer["tool"]["description"]:
                # Ask the user to change the tool
                mb.hold(['x', 'y'])
                print("Please put the following tool : " + layer["tool"]["description"])
                waitKey()
                currentTool = layer["tool"]["description"]

            # Levelling
            minX = project["minX"] + offset['x']
            minY = project["minY"] + offset['y']
            maxX = project["maxX"] + offset['x']
            maxY = project["maxY"] + offset['y']
            centerX = (minX + maxX) / 2.
            centerY = (minY + maxY) / 2.
            mb.move(centerX, centerY)
            mb.moveZ(70)
            print("Now we will level the buildplate.")
            print("Please tighten the levelling screws under the buildplate")
            waitKey()
            print("Use the up and down keys to raise the buildplate to about 1mm from the tool, then press Enter")
            print("You can use the + and - keys to adjust the step size")
            fifo = [0, 0, 0]
            speed = 500
            step = 2
            steps = [0.1, 0.5, 1, 2, 5, 10]
            while True:
                sys.stdout.write("\rstep : " + str(steps[step]) + "mm, Z : " + str(mb.position['z']) + "mm   ")
                mb.wait()
                key = ord(getch())
                fifo[2] = fifo[1]
                fifo[1] = fifo[0]
                fifo[0] = key
                if key == 3:
                    print("")
                    return
                elif key == 13:
                    print("")
                    break
                elif fifo[2] == 27 and fifo[1] == 91:
                    # Escaping sequence
                    if fifo[0] == 65: # Up
                        mb.moveZ(steps[step], speed=speed, relative=True)
                    elif fifo[0] == 66: # Down
                        mb.moveZ(-steps[step], speed=speed, relative=True)
                elif key == ord("+"):
                    if step < len(steps):
                        step += 1
                elif key == ord("-"):
                    if step > 0:
                        step -= 1
            buildplateZ = mb.position['z']
            print("Fine-tune the levelling by untightening the screws until the tool barely touches")
            mb.moveZ(buildplateZ - travelHeight, speed)
            mb.move(minX, minY)
            mb.moveZ(buildplateZ, speed)
            mb.wait()
            waitKey()
            mb.moveZ(buildplateZ - travelHeight, speed)
            mb.move(maxX, minY)
            mb.wait()
            mb.moveZ(buildplateZ, speed)
            waitKey()
            mb.moveZ(buildplateZ - travelHeight, speed)
            mb.move(centerX, maxY)
            mb.moveZ(buildplateZ, speed)
            mb.wait()
            waitKey()

            # Move back to origin
            mb.moveZ(buildplateZ - travelHeight)
            mb.wait()
            x = minX
            if isReversed:
                x = reversedOriginX - x
            mb.move(x, minY)
        
        # Ask the user to start the motor
        print("When you are ready, put your safety glasses on, start the motor and press Enter!")
        waitKey()

        # Send order sequences
        print("Building, please don't interrupt...")
        print "0%",
        feedrate = 3000
        travelSpeed = 500
        zspeedUp = 400
        zspeedDown = 3000
        up = True
        n = len(orders[layerId])
        i = 0
        for order in orders[layerId]:
            print "\r" + str(int(i * 100 / n)) + "%",
            sys.stdout.flush()
            if len(order) == 1:
                speed = 0
                if order[0] > 0:
                    up = True
                    speed = zspeedUp
                else:
                    up = False
                    speed = zspeedDown
                mb.wait()
                mb.moveZ(buildplateZ - order[0], speed)
                mb.wait()
            elif len(order) == 2:
                speed = 0
                if up:
                    speed = travelSpeed
                else:
                    speed = feedrate
                x = offset['x'] + order[0]
                y = offset['y'] + order[1]
                if isReversed:
                    x = reversedOriginX - x
                mb.move(x, y, speed)
            i += 1

        # Move back to origin
        mb.moveZ(buildplateZ - travelHeight)
        mb.wait()
        x = offset['x']
        y = offset['y']
        if isReversed:
            x = reversedOriginX - x
        mb.move(x, y)

        wasLastReversed = isReversed

    mb.release()
    mb.moveZ(0)
    print("")
    print("Done!")


def cmd_exit(args=None):
    if project["name"] != "":
        saveProject()
    print("Bye!")
    sys.exit(0)

if __name__ == "__main__":
    # Welcome message
    print("Hi! What do you want to make today?")

    # Try to find a machine and connect to it
    mb.autoConnect()

    # Try to load an existing project
    autoLoadProject()

    while True:
        try:
            command = raw_input(project["name"] + "> ").split()
        except (EOFError, KeyboardInterrupt):
            cmd_exit()
        if len(command) > 0:
            if command[0] in commands:
                locals()["cmd_" + command[0]](command)
            else:
                print("Unknown command : " + command[0])