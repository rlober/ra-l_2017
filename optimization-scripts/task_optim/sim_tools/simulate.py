import subprocess
import time
import shlex
import yarp

def killProcesses():
    proc_list = ["yarpserver", "gzserver", "gzclient", "ocra-icub-server", "reach-client", "stand-client"]
    total_killed = 0
    for p in proc_list:
        args = ["pkill", "-c", "-9", p]
        output,error = subprocess.Popen(args,stdout = subprocess.PIPE, stderr= subprocess.PIPE).communicate()
        total_killed += int(output)
    if total_killed > 0:
        print("Killed " + str(total_killed) +" processes")
    else:
        print("No processes were killed.")

    return total_killed

def simulate(controllerArgs, clientArgs, icubWorldPath, savePath=None, verbose=False, visual=False, askUserForReplay=False, runningRemotely=False):

    replay = True
    while replay:

        if verbose:
            print('Starting script...')
        if verbose:
            print('-- Launching yarpserver')
        yarp = subprocess.Popen(["yarpserver", "--write"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

        if verbose:
            print('-- Launching gzserver with icub.world @', icubWorldPath)

        gz_args = ["gzserver"]
        if runningRemotely:
            import os
            os.environ["DISPLAY"] = ":0"

        gz_args.append(icubWorldPath)
        gzserver = subprocess.Popen(gz_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if visual:
            if verbose:
                print('-- Launching visuals with gzclient.')
            gzclient = subprocess.Popen(["gzclient"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(4)


        ctrl_args = shlex.split(controllerArgs)
        if verbose:
            print('-- Launching ocra-icub-server with args: ', ctrl_args)
        controller = subprocess.Popen(ctrl_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(5)

        if savePath != None:
            clientArgs += " --savePath " + savePath

        clArgs = shlex.split(clientArgs)
        if verbose:
            print('-- Launching client with args: ', clArgs)
        client = subprocess.Popen(clArgs, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        timeout = 40.0
        try:
            client.wait(timeout)
        except:
            client.kill()

        #### REPLAY STUFF ####

        if visual and askUserForReplay:
            user_input = input("Replay simulation? [y/n] (y): ")
            if user_input == "" or user_input == "y" or user_input == "Y":
                replay = True
            else:
                replay = False
        else:
            replay = False

        ######################

        timeout = 20.0
        if verbose:
            print('-- Terminating controller')
        controller.terminate()
        try:
            controller.wait(timeout)
        except:
            controller.kill()
        if verbose:
            print('-- Terminating gzserver')

        if runningRemotely:
            time.sleep(10)

        gzserver.terminate()
        if visual:
            gzclient.terminate()

        try:
            gzserver.wait(timeout)
        except:
            gzserver.kill()

        if visual:
            try:
                gzclient.wait(timeout)
            except:
                gzclient.kill()

        if verbose:
            print('-- Cleaning up ports')
        args1 = "yarp clean"
        args = shlex.split(args1)
        cleanYarp = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            cleanYarp.wait(timeout)
        except:
            cleanYarp.kill()
        if verbose:
            print('-- Terminating yarpserver')
        yarp.terminate()

class GazeboSimulation():
    """A persistant yarp and gazebo process manager"""
    def __init__(self, world_file_path, verbose=False, visual=False):
        assert(world_file_path is not None)
        self.world_file_path = world_file_path
        self.verbose = verbose
        self.visual = visual
        self.yarp_net = yarp.Network()
        self.yarp_net.init()
        self.rpc_port = yarp.RpcClient()
        self.rpc_port_name = "/python/GazeboSimulation/wholeBodyDynamicsTree/rpc:o"
        self.rpc_port.open(self.rpc_port_name)

        self.launch()

    def __del__(self):
        self.close()

    def launch(self):
        if self.verbose:
            print('-- Launching gzserver with icub.world @', self.world_file_path)

        gz_args = ["gzserver", "-slibgazebo_yarp_clock.so", self.world_file_path, "--verbose"]
        self.gzserver = subprocess.Popen(gz_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if self.visual:
            if self.verbose:
                print('-- Launching visuals with gzclient.')
            self.gzclient = subprocess.Popen(["gzclient"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(2.0)

        if self.verbose:
            print('-- Launching wholeBodyDynamicsTree.')
        self.wbdtree = subprocess.Popen(["wholeBodyDynamicsTree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        time.sleep(5.0)

        if self.yarp_net.connect(self.rpc_port_name, "/wholeBodyDynamicsTree/rpc:i"):
            self.recalibrateWBDTree()
        else:
            print("[ERROR] Couldn't re-calibrate the wholeBodyDynamicsTree.")

    def recalibrateWBDTree(self):
        msg_btl = yarp.Bottle()
        reply_btl = yarp.Bottle()
        msg_btl.addString("resetOffset")
        msg_btl.addString("all")
        self.rpc_port.write(msg_btl, reply_btl)

    def reset(self):
        if self.verbose:
            print("-- Resetting gazebo simulation environment.")
        subprocess.Popen(["gz", "world", "-r"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.cleanUpYarp()
        time.sleep(1.0)
        self.recalibrateWBDTree()


    def cleanUpYarp(self):
        if self.verbose:
            print('-- Cleaning up ports')
        args1 = "yarp clean --timeout 0.1"
        args = shlex.split(args1)
        cleanYarp = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


    def close(self):
        timeout = 5.0
        self.rpc_port.close()
        if self.verbose:
            print('-- Terminating gzserver')

        self.gzserver.terminate()

        if self.verbose:
            print('-- Terminating wholeBodyDynamicsTree')

        self.wbdtree.terminate()

        if self.visual:
            if self.verbose:
                print('-- Terminating gzclient')
            self.gzclient.terminate()

        try:
            self.gzserver.wait(timeout)
        except:
            self.gzserver.kill()
        try:
            self.wbdtree.wait(timeout)
        except:
            self.wbdtree.kill()

        if self.visual:
            try:
                self.gzclient.wait(timeout)
            except:
                self.gzclient.kill()
