import matplotlib.pyplot as plt
import matplotlib.collections as plt_collections
from matplotlib.widgets import Button
import csv

csvFilaPath = 'log.csv'


rpm_id = '0x204'
speed_id = '0x202'


class FrameStream:
    def __init__(self):
        self.timeStream = []
        self.bytesStream = []  # array of [8]
        self.constTimestamps = []  # array of [8](start, end) tuples


frames = dict()

with open(csvFilaPath, 'r') as file:
    rows = csv.reader(file, delimiter=',')
    for row in rows:
        if len(row) < 3 or not row[0].startswith('0x'):
            print('skip row:', row)
            continue
        id = row[0]
        try:
            time = int(row[1])
        except ValueError:
            print('incorrect row time:', row)
            continue
        try:
            # base-16 is required to convert hex to int
            bytes = [int(x, 16) for x in row[2:]]
        except ValueError:
            print('incorrect row numbers:', row)
            continue
        if not id in frames:
            frames[id] = FrameStream()
        frame = frames[id]
        if len(frame.bytesStream) == 0:
            frame.bytesStream = [[x] for x in bytes]
        else:
            if len(bytes) != len(frame.bytesStream):
                continue # frame damaged
            for b, byte in enumerate(bytes):
                frame.bytesStream[b].append(byte)
        frame.timeStream.append(time)
        assert len(frame.timeStream) == len(frame.bytesStream[0])

print('CSV parsed')

errorsCount = 0
for (_, frame) in list(frames.items()):
    for byteStream in frame.bytesStream:
        for i, b5 in enumerate(zip(byteStream[:-4], byteStream[1:-3], byteStream[2:-2], byteStream[3:-1], byteStream[4:])):
            if b5[2] != b5[0] and b5[0] == b5[1] and b5[0] == b5[3] and b5[0] == b5[4]:
                byteStream[i+2] = b5[0]
                errorsCount += 1

print('errors fixed (bytes):', errorsCount)

# calculate constancy intervals (means how much time the byte keeps constant bitmask):
for (_, frame) in list(frames.items()):
    for byteStream in frame.bytesStream:
        frame.constTimestamps.append(list())
        if len(set(byteStream)) > 10:
            continue  # skip bytes with real numeric data
        timeStart = 0
        for i, b2 in enumerate(zip(byteStream[:-1], byteStream[1:])):
            if (b2[0] != b2[1]) or (i == len(byteStream) - 2):
                if timeStart < (i - 10):
                    frame.constTimestamps[-1].append([timeStart, i])
                timeStart = i+1

for key, frame in frames.items():
    print(key, "constant intervals: [", ', '.join([str(len(x)) for x in frame.constTimestamps]), "]")

# make 4 subplots with shared X axis:
fig, axs = plt.subplots(4, 1, sharex='all')
plt.xlim(list(frames.values())[0].timeStream[0] * 0.001, list(frames.values())[0].timeStream[-1] * 0.001)
# fig.tight_layout() - brakes buttons
plt.subplots_adjust(left=0.05, right=0.99, top=0.9, bottom=0.1)

# display graphs of parsed and calculated RPM, Torque, etc. :
axs[0].set_title('RPM & Throttle Position Parsed (0x204)')
x = [time * 0.001 for time in frames[rpm_id].timeStream]
y = [(b1_b2[0]*256 + b1_b2[1]) * 2 / 10 for b1_b2 in zip(frames[rpm_id].bytesStream[3], frames[rpm_id].bytesStream[4])]
axs[0].plot(x, y, label='RPM /10')

# throttle position
x = [time * 0.001 for time in frames[rpm_id].timeStream]
# will show what * the pedal was down amplified by 100. 500 means pedal fully down
y = [(b1_b22[0] * 256 + b1_b22[1]) / 65792 * 500 for b1_b22 in zip(frames[rpm_id].bytesStream[1], frames[rpm_id].bytesStream[2])]
axs[0].plot(x, y, label='Throttle', alpha=0.5)
axs[0].fill_between(x, 0, y, label='Throttle', facecolor='green', alpha=0.25)


# dispaly speed steering angle and L/R forces:
axs[1].set_title('Speed (MPH) (0x202)')
x = [time * 0.001 for time in frames[speed_id].timeStream]
y = [(b1_b21[0]*256 + b1_b21[1]) / 175 for b1_b21 in zip(frames[speed_id].bytesStream[6], frames[speed_id].bytesStream[7])]
axs[1].plot(x, y, label='Speed (mph)')





def displayCustomFrame(frameId):
    # display raw values of 8 bytes of specified CAN ID, skip constant and noise bytes:
    bytesCount = len(frames[frameId].bytesStream)
    axs[2].set_title(frameId + ': ' + str(bytesCount) + ' bytes')
    x = [time * 0.001 for time in frames[frameId].timeStream]
    for i in range(0, bytesCount):
        y = frames[frameId].bytesStream[i]
        dy = [v1_v2[1]-v1_v2[0] for v1_v2 in zip(y, y[1:])]
        avr = sum([abs(x) for x in dy])
        if avr == 0:
            print(frameId, 'skip constant byte', i)
            continue  # skip constant byte
        avr /= len(dy)
        if avr > 5:
            print(frameId, 'skip noise byte', i)
            continue  # skip noise
        axs[2].plot(x, y, label='Byte ' + str(i))
    axs[2].legend(fontsize='x-small')

    axs[3].set_title(frameId + ' constant values intervals')
    axs[3].yaxis.set_visible(False)
    frame = frames[frameId]
    for b, byteTimestamps in enumerate(frame.constTimestamps):
        if len(byteTimestamps) == 0:
            continue
        axs[3].text(1, b + 0.5, 'b' + str(b), va='center', color='black', fontsize='x-small')
        prevTimeStart = frame.timeStream[byteTimestamps[0][0]] * 0.001
        for i, timestamp in enumerate(byteTimestamps):
            timeStart = frame.timeStream[timestamp[0]] * 0.001
            timeEnd = frame.timeStream[timestamp[1]] * 0.001
            axs[3].barh(y=b, width=timeEnd - timeStart, left=prevTimeStart, color=('yellow' if i % 2 == 0 else 'lime'))
            prevTimeStart = timeEnd
            byteValue = frame.bytesStream[b][timestamp[0]]
            axs[3].text((timeStart + timeEnd) / 2, b + 0.5, str(byteValue), ha='center', va='center', color='black', fontsize='x-small')
    axs[3].legend(fontsize='x-small')

axs[0].legend(fontsize='x-small')
axs[1].legend(fontsize='x-small')

frameIdIndex= 0
frameId = list(frames.keys())[frameIdIndex]
def nextClick(event):
    global frameId
    global frameIdIndex
    axs[2].clear()
    axs[3].clear()
    frameIdIndex = (frameIdIndex + 1) % len(frames)
    frameId = list(frames.keys())[frameIdIndex]
    displayCustomFrame(frameId)
    plt.draw()
def prevClick(event):
    global frameId
    global frameIdIndex
    axs[2].clear()
    axs[3].clear()
    frameIdIndex = (frameIdIndex - 1) % len(frames)
    frameId = list(frames.keys())[frameIdIndex]
    displayCustomFrame(frameId)
    plt.draw()
axprev = plt.axes([0.88, 0.01, 0.05, 0.05])
bprev = Button(axprev, '<')
bprev.on_clicked(prevClick)
axnext = plt.axes([0.94, 0.01, 0.05, 0.05])
bnext = Button(axnext, '>')
bnext.on_clicked(nextClick)

fig.suptitle(csvFilaPath)
displayCustomFrame(frameId)
plt.show()
