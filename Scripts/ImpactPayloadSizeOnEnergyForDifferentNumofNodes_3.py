import datetime

import numpy as np
import simpy

import PropagationModel
from AirInterface import AirInterface
from EnergyProfile import EnergyProfile
from Gateway import Gateway
from Global import Config
from LoRaParameters import LoRaParameters
from Location import Location
from Node import Node
from SNRModel import SNRModel

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# The console attempts to auto-detect the width of the display area, but when that fails it defaults to 80 characters. This behavior can be overridden with:
desired_width = 320
pd.set_option('display.width', desired_width)

transmission_rate = 0.02e-3  # 12*8 bits per hour (1 typical packet per hour)
simulation_time = 1000 * 50 / transmission_rate
cell_size = 1000
adr = True
confirmed_messages = True


def plot_time(_env):
    while True:
        print('.', end='', flush=True)
        yield _env.timeout(np.round(simulation_time / 10))


tx_power_mW = {2: 91.8, 5: 95.9, 8: 101.6, 11: 120.8, 14: 146.5}  # measured TX power for each possible TP
middle = np.round(Config.CELL_SIZE / 2)
gateway_location = Location(x=middle, y=middle, indoor=False)

payload_sizes = range(5, 55, 5)
num_of_nodes = [100]  # [100, 500, 1000, 2000, 5000, 10000]
max_num_nodes = max(num_of_nodes)
num_of_simulations = 1

simultation_results = dict()
gateway_results = dict()
air_interface_results = dict()

for num_nodes in num_of_nodes:
    simultation_results[num_nodes] = pd.DataFrame()
    gateway_results[num_nodes] = pd.DataFrame()
    air_interface_results[num_nodes] = pd.DataFrame()

for n_sim in range(num_of_simulations):

    locations = list()
    for i in range(max_num_nodes):
        locations.append(Location(min=0, max=cell_size, indoor=False))

    for num_nodes in num_of_nodes:

        for payload_size in payload_sizes:

            env = simpy.Environment()
            gateway = Gateway(env, gateway_location)
            nodes = []
            air_interface = AirInterface(gateway, PropagationModel.LogShadow(), SNRModel(), env)
            np.random.shuffle(locations)
            for node_id in range(num_nodes):
                energy_profile = EnergyProfile(5.7e-3, 15, tx_power_mW,
                                               rx_power={'pre_mW': 8.2, 'pre_ms': 3.4, 'rx_lna_on_mW': 39,
                                                         'rx_lna_off_mW': 34,
                                                         'post_mW': 8.3, 'post_ms': 10.7})
                lora_param = LoRaParameters(freq=np.random.choice(LoRaParameters.DEFAULT_CHANNELS),
                                            sf=np.random.choice(LoRaParameters.SPREADING_FACTORS),
                                            bw=125, cr=5, crc_enabled=1, de_enabled=0, header_implicit_mode=0, tp=14)
                node = Node(node_id, energy_profile, lora_param, sleep_time=(8 * payload_size / transmission_rate),
                            process_time=5,
                            adr=adr,
                            location=locations[node_id],
                            base_station=gateway, env=env, payload_size=payload_size, air_interface=air_interface,
                            confirmed_messages=confirmed_messages)
                nodes.append(node)
                env.process(node.run())

            # END adding nodes to simulation
            env.process(plot_time(env))

            d = datetime.timedelta(milliseconds=simulation_time)
            print('Running simulator for {}.'.format(d))
            env.run(until=simulation_time)
            print('Simulator is done for payload size {}'.format(payload_size))

            data = Node.get_mean_simulation_data_frame(nodes, name=payload_size) / (num_nodes * num_of_simulations)
            # print(data)
            simultation_results[num_nodes] = simultation_results[num_nodes].append(data)
            data = gateway.get_simulation_data(name=payload_size) / (num_nodes*num_of_simulations)
            gateway_results[num_nodes] = gateway_results[num_nodes].append(data)
            data = air_interface.get_simulation_data(name=payload_size) / (num_nodes*num_of_simulations)
            air_interface_results[num_nodes] = air_interface_results[num_nodes].append(data)

        simultation_results[num_nodes]['UniqueBytes'] = simultation_results[num_nodes].UniquePackets * \
                                                        simultation_results[num_nodes].index.values
        simultation_results[num_nodes]['CollidedBytes'] = simultation_results[num_nodes].CollidedPackets * \
                                                          simultation_results[num_nodes].index.values
        print(simultation_results[num_nodes])
        print(gateway_results[num_nodes])
        print(air_interface_results[num_nodes])
        # END loop payload_sizes

        # Printing experiment parameters
        print('{} nodes in network'.format(num_nodes))
        print('{} transmission rate'.format(transmission_rate))
        print('{} ADR'.format(adr))
        print('{} confirmed msgs'.format(confirmed_messages))
        print('{}m cell size'.format(cell_size))

# END loop num_of_nodes


sns.set_style("ticks")
# set width of bar
barWidth = 0.25

CollidedPackets = simultation_results[num_of_nodes[0]].CollidedPackets
RetransmittedPackets = simultation_results[num_of_nodes[0]].RetransmittedPackets
NoDLReceived = simultation_results[num_of_nodes[0]].NoDLReceived

# Set position of bar on X axis
r1 = np.arange(len(CollidedPackets))
r2 = [x + barWidth for x in r1]
r3 = [x + barWidth for x in r2]

# Make the plot
plt.bar(r1, CollidedPackets, color='#7f6d5f', width=barWidth, edgecolor='white', label='var1')
plt.bar(r2, RetransmittedPackets, color='#557f2d', width=barWidth, edgecolor='white', label='var2')
plt.bar(r3, NoDLReceived, color='#2d7f5e', width=barWidth, edgecolor='white', label='var3')

# Create legend & Show graphic
plt.legend()
plt.show()
