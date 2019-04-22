import os, inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(os.path.dirname(currentdir))
os.sys.path.insert(0, parentdir)

import math
import gym
import time
from gym import spaces
from gym.utils import seeding
import numpy as np
import pybullet
# from
# from pybullet import racecar
# from pybullet_envs import racecar
from agent_env_classes.obj_physics_models import Racecar, Vector
import random
# from pybullet import bullet_client
import pybullet_utils.bullet_client as bullet_client
import pybullet_data
from pkg_resources import parse_version

RENDER_HEIGHT = 720
RENDER_WIDTH = 960

class VectorBulletEnv(gym.Env):
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second': 50
    }

    def __init__(self,
                 urdfRoot=pybullet_data.getDataPath(),
                 actionRepeat=50,
                 isEnableSelfCollision=True,
                 isDiscrete=False,
                 renders=False):
        print("init")
        self._timeStep = 0.01
        self._urdfRoot = urdfRoot
        self._actionRepeat = actionRepeat
        self._isEnableSelfCollision = isEnableSelfCollision
        self._observation = []
        self._ballUniqueId = -1
        self._envStepCounter = 0
        self._renders = renders
        self._isDiscrete = isDiscrete
        if self._renders:
            self._p = bullet_client.BulletClient(
                connection_mode=pybullet.GUI)
        else:
            self._p = bullet_client.BulletClient()

        self.seed()
        # self.reset()
        observationDim = 2  # len(self.getExtendedObservation())
        # print("observationDim")
        # print(observationDim)
        # observation_high = np.array([np.finfo(np.float32).max] * observationDim)
        observation_high = np.ones(observationDim) * 1000  # np.inf
        if (isDiscrete):
            self.action_space = spaces.Discrete(9)
        else:
            action_dim = 2
            self._action_bound = 1
            action_high = np.array([self._action_bound] * action_dim)
            self.action_space = spaces.Box(-action_high, action_high, dtype=np.float32)
        self.observation_space = spaces.Box(-observation_high, observation_high, dtype=np.float32)
        self.viewer = None

    def reset(self):
        self._p.resetSimulation()
        # p.setPhysicsEngineParameter(numSolverIterations=300)
        self._p.setTimeStep(self._timeStep)
        # self._p.loadURDF(os.path.join(self._urdfRoot,"plane.urdf"))
        stadiumobjects = self._p.loadSDF(os.path.join(self._urdfRoot, "stadium.sdf"))
        # move the stadium objects slightly above 0
        # for i in stadiumobjects:
        #	pos,orn = self._p.getBasePositionAndOrientation(i)
        #	newpos = [pos[0],pos[1],pos[2]-0.1]
        #	self._p.resetBasePositionAndOrientation(i,newpos,orn)

        dist = 5 + 2. * random.random()
        ang = 2. * 3.1415925438 * random.random()

        ballx = dist * math.sin(ang)
        bally = dist * math.cos(ang)
        ballz = 1

        self._ballUniqueId = self._p.loadURDF(os.path.join(self._urdfRoot, "sphere2.urdf"),
                                              # todo get cup
                                              [ballx, bally, ballz])
        self._p.setGravity(0, 0, -10)
        # self._racecar = Racecar(self._p, urdfRootPath=self._urdfRoot,
        #                                 timeStep=self._timeStep)
        self._racecar = Vector(self._p, urdfRootPath=self._urdfRoot,
                               timeStep=self._timeStep)
        self._envStepCounter = 0
        for i in range(100):
            self._p.stepSimulation()
        self._observation = self.getExtendedObservation()
        return np.array(self._observation)

    def __del__(self):
        self._p = 0

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def getExtendedObservation(self):
        self._observation = []  # self._racecar.getObservation()
        carpos, carorn = self._p.getBasePositionAndOrientation(self._racecar.racecarUniqueId)
        ballpos, ballorn = self._p.getBasePositionAndOrientation(self._ballUniqueId)
        invCarPos, invCarOrn = self._p.invertTransform(carpos, carorn)
        ballPosInCar, ballOrnInCar = self._p.multiplyTransforms(invCarPos, invCarOrn, ballpos,
                                                                ballorn)

        self._observation.extend([ballPosInCar[0], ballPosInCar[1]])
        return self._observation

    def step(self, action):
        print(self._timeStep)
        if (self._renders):
            basePos, orn = self._p.getBasePositionAndOrientation(self._racecar.racecarUniqueId)
            # self._p.resetDebugVisualizerCamera(1, 30, -40, basePos)

        # import pdb;pdb.set_trace()
        if (self._isDiscrete):
            # fwd = [-1, -1, -1, 0, 0, 0, 1, 1, 1]
            # steerings = [-0.6, 0, 0.6, -0.6, 0, 0.6, -0.6, 0, 0.6]
            # forward = fwd[action]
            # steer = steerings[action]
            # realaction = [forward, steer]

            realaction = action
        else:
            realaction = action

        self._racecar.applyAction(realaction)
        for i in range(self._actionRepeat):
            self._p.stepSimulation()
            if self._renders:
                time.sleep(self._timeStep)
            self._observation = self.getExtendedObservation()

            if self._termination():
                break
            self._envStepCounter += 1
        reward = self._reward()
        done = self._termination()
        # print("len=%r" % len(self._observation))

        return np.array(self._observation), reward, done, {}

    def render(self, mode='human', close=False):
        if mode != "rgb_array":
            return np.array([])
        base_pos, orn = self._p.getBasePositionAndOrientation(self._racecar.racecarUniqueId)
        view_matrix = self._p.computeViewMatrixFromYawPitchRoll(
            cameraTargetPosition=base_pos,
            distance=self._cam_dist,
            yaw=self._cam_yaw,
            pitch=self._cam_pitch,
            roll=0,
            upAxisIndex=2)
        proj_matrix = self._p.computeProjectionMatrixFOV(
            fov=60, aspect=float(RENDER_WIDTH) / RENDER_HEIGHT,
            nearVal=0.1, farVal=100.0)
        (_, _, px, _, _) = self._p.getCameraImage(
            width=RENDER_WIDTH, height=RENDER_HEIGHT, viewMatrix=view_matrix,
            projectionMatrix=proj_matrix, renderer=pybullet.ER_BULLET_HARDWARE_OPENGL)
        rgb_array = np.array(px)
        rgb_array = rgb_array[:, :, :3]
        return rgb_array

    def _termination(self):
        return self._envStepCounter > 1000

    def _reward(self):
        closestPoints = self._p.getClosestPoints(self._racecar.racecarUniqueId, self._ballUniqueId,
                                                 10000)

        numPt = len(closestPoints)
        reward = -1000
        # print(numPt)
        if (numPt > 0):
            # print("reward:")
            reward = -closestPoints[0][8]
            # print(reward)
        return reward

    if parse_version(gym.__version__) < parse_version('0.9.6'):
        _render = render
        _reset = reset
        _seed = seed
        _step = step


# env = VectorBulletEnv(isDiscrete=False, renders=True)
# env = VectorBulletEnv(isDiscrete=True, renders=True)
#
# env.reset()
#
# for i in range(100000):
#     # image = env.render()
#     action = env.action_space.sample()
#     state, reward, done, info = env.step(action)








import sys

sys.exit()
import math
import time

import numpy as np
import pybullet as p

cid = p.connect(p.SHARED_MEMORY)
if (cid < 0):
    p.connect(p.GUI)

p.resetSimulation()
p.setGravity(0, 0, -10)
useRealTimeSim = 1

# for video recording (works best on Mac and Linux, not well on Windows)
# p.startStateLogging(p.STATE_LOGGING_VIDEO_MP4, "racecar.mp4")
p.setRealTimeSimulation(useRealTimeSim)  # either this
p.loadURDF("plane.urdf")
# p.loadSDF("stadium.sdf")

# car = p.loadURDF("data/racecar_differential.urdf")  # , [0,0,2],useFixedBase=True)
car = p.loadSDF("model.sdf", globalScaling=3.0)  # , [0,0,2],useFixedBase=True)
print(car)
car = car[0]
print(p.getNumJoints(car))
for i in range(p.getNumJoints(car)):
    print(p.getJointInfo(car, i))
for wheel in range(p.getNumJoints(car)):
    p.setJointMotorControl2(car, wheel, p.VELOCITY_CONTROL, targetVelocity=0, force=0)
    p.getJointInfo(car, wheel)

# sys.exit()
p.resetBasePositionAndOrientation(car, [0, 0, 0.5], [0, 0, 0, 1])

pixelWidth = 320
pixelHeight = 220
# camDistance = 4
# camDistance = 0.5
# upAxisIndex = 2
camera_height = 0.9

wheels = [8, 15]
print("----------------")

# p.setJointMotorControl2(car,10,p.VELOCITY_CONTROL,targetVelocity=1,force=10)
# c = p.createConstraint(car, 9, car, 11, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=1, maxForce=10000)
#
# c = p.createConstraint(car, 10, car, 13, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=-1, maxForce=10000)
#
# c = p.createConstraint(car, 9, car, 13, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=-1, maxForce=10000)
#
# c = p.createConstraint(car, 16, car, 18, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=1, maxForce=10000)
#
# c = p.createConstraint(car, 16, car, 19, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=-1, maxForce=10000)
#
# c = p.createConstraint(car, 17, car, 19, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=-1, maxForce=10000)
#
# c = p.createConstraint(car, 1, car, 18, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=-1, gearAuxLink=15, maxForce=10000)
# c = p.createConstraint(car, 3, car, 19, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
#                        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
# p.changeConstraint(c, gearRatio=-1, gearAuxLink=15, maxForce=10000)

steering = [0, 2]

# for vector
'''
(3, b'anki_vector::anki_vector::robot::wheel_BL_hinge'
(4, b'anki_vector::anki_vector::robot::wheel_BR_hinge'
(5, b'anki_vector::anki_vector::robot::wheel_FL_hinge'
(6, b'anki_vector::anki_vector::robot::wheel_FR_hinge'
'''
wheels = [3, 4, 5, 6]
wheels = [3, 5]
# wheels = [3, 4]
right_side_wheels = [4, 6]
# steering = [3]
# steering = []

targetVelocitySlider = p.addUserDebugParameter("wheelVelocity", -50, 50, 0)
maxForceSlider = p.addUserDebugParameter("maxForce", 0, 50, 20)
steeringLeftSlider = p.addUserDebugParameter("steeringleft", -1, 1, 0)
steeringRightSlider = p.addUserDebugParameter("steeringright", -1, 1, 0)
t = 0
value_to_add = 0.0
while (True):
    maxForce = p.readUserDebugParameter(maxForceSlider)
    targetVelocity = p.readUserDebugParameter(targetVelocitySlider)
    steeringLeftVel = p.readUserDebugParameter(steeringLeftSlider)
    steeringRightVel = p.readUserDebugParameter(steeringRightSlider)

    for wheel in wheels:
        p.setJointMotorControl2(car, wheel, p.VELOCITY_CONTROL, targetVelocity=targetVelocity,
                                force=maxForce)

    for wheel in right_side_wheels:
        p.setJointMotorControl2(car, wheel, p.VELOCITY_CONTROL, targetVelocity=-targetVelocity,
                                force=maxForce)

    # for steer in steering:
    #     p.setJointMotorControl2(car, steer, p.POSITION_CONTROL, targetPosition=-steeringAngle)

    # for steer in steering:
    # p.setJointMotorControl2(car, 3, p.VELOCITY_CONTROL, targetVelocity=targetVelocity + steeringLeftVel)
    # p.setJointMotorControl2(car, 4, p.VELOCITY_CONTROL, targetVelocity=targetVelocity + steeringRightVel)

    # if t % 200 == 0:
    car_orientation = p.getBasePositionAndOrientation(car)
    x_y_z = list(car_orientation[0])
    x_y_z[2] += camera_height
    quaternion_pose = car_orientation[1]
    # print()
    cameraUpVector = [0, 0, 1]
    # target_position = [0, 0, 0]
    euler_angle_pose = p.getEulerFromQuaternion(quaternion_pose)
    multiplier = 4.0
    multiplier = 40.0
    pitch = euler_angle_pose[0]
    roll = euler_angle_pose[1]
    yaw = euler_angle_pose[2]

    front_vector = [math.cos(yaw) * math.cos(pitch),
                    math.sin(yaw),
                    math.cos(yaw) * math.sin(pitch)]

    front_vector = (np.array(front_vector) / np.linalg.norm(front_vector)).tolist()

    target_position = [x_y_z[0] + multiplier * front_vector[0],
                       x_y_z[1] + multiplier * front_vector[1],
                       x_y_z[2] + multiplier * front_vector[2]]

    viewMatrix = p.computeViewMatrix(x_y_z, target_position, cameraUpVector)

    projectionMatrix = [1.0825318098068237, 0.0, 0.0, 0.0, 0.0, 1.732050895690918, 0.0, 0.0,
                        0.0,
                        0.0, -1.0002000331878662, -1.0, 0.0, 0.0, -0.020002000033855438, 0.0]

    img_arr = p.getCameraImage(pixelWidth, pixelHeight, viewMatrix=viewMatrix,
                               projectionMatrix=projectionMatrix,
                               shadow=1,
                               lightDirection=[1, 1, 1]
                               )

    # todo PyBullet.isNumpyEnabled(

    keys = p.getKeyboardEvents()
    if keys.get(100):
        pass

    if (useRealTimeSim == 0):
        p.stepSimulation()
    time.sleep(0.01)

    t += 1
