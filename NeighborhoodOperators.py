from CrewSchedule import CrewSchedule
from CrewDuty import CrewDuty
import copy

def swapNeighborhoodOperator(duty1, task1, duty2, task2):

    if task1["origin"] == task2["origin"] and task1["destination"] == task2["destination"]:
        new_duty1 = copy.deepcopy(duty1)
        new_duty2 = copy.deepcopy(duty2)
        new_task1 = copy.deepcopy(task1)
        new_task2 = copy.deepcopy(task2)

        #define a neighborhood operator that swaps tasks between duties in order to get a solution that is closer to original schedule
        new_duty1.remove_task(new_task1)
        new_duty2.insert_task(new_task1)
        new_duty2.remove_task(new_task2)
        new_duty1.insert_task(new_task2)

        if new_duty1.check_feasibility() and new_duty2.check_feasibility():
            return [new_duty1, new_duty2]
        else:
            return False
    else:
        return False

def removeInsertNeighborhoodOperator(duty1, task1, duty2):
    new_duty1 = copy.deepcopy(duty1)
    new_duty2 = copy.deepcopy(duty2)
    new_task1 = copy.deepcopy(task1)

    new_duty1.remove_task(new_task1)
    new_duty2.insert_task(new_task1)
    if new_duty1.check_feasibility() and new_duty2.check_feasibility():
        return [new_duty1, new_duty2]
    else:
        return False

#this function returns a list of blocks, represented by lists of tasks, of which each block is operated on the same train - there must be at least two tasks on the same train to count as a block
def identifyTrainBlocks(duty, id_mapping):
    identified_blocks = []

    block_identified = False
    for i, current_task in enumerate(duty.tasks[:-1]):  # Exclude the last item
        next_task = duty.tasks[i + 1]
        current_train = id_mapping[current_task["id"]]["locomotive"]
        next_train = id_mapping[next_task["id"]]["locomotive"]
        #there was no block before but now we found one
        if (block_identified == False and current_train == next_train):
            new_block = [copy.deepcopy(current_task), copy.deepcopy(next_task)]
            block_identified = True
        #there is already a block and we found a new task in the block
        elif (block_identified == True and current_train == next_train):
            new_block.append(copy.deepcopy(next_task))
        #there was a block, but the next task is from another train
        elif (block_identified == True and current_train != next_train):
            identified_blocks.append(new_block)
            block_identified = False
    return identified_blocks



#block1 is represented as a list of tasks that are performed on the same train
def removeInsertTrainBlockNeighborhoodOperator(duty1, block1, duty2):
    new_duty1 = copy.deepcopy(duty1)
    new_duty2 = copy.deepcopy(duty2)

    new_block1 = []
    for task in block1:
        new_block1.append(copy.deepcopy(task))

    for task in new_block1:
        new_duty1.remove_task(task)
    for task in new_block1:
        new_duty2.insert_task(task)

    if new_duty1.check_feasibility() and new_duty2.check_feasibility():
        return [new_duty1, new_duty2]
    else:
        return False

def doubleRemoveInsertNeighborhoodOperator(duty1, task1, task2, duty2):
    new_duty1 = copy.deepcopy(duty1)
    new_duty2 = copy.deepcopy(duty2)
    new_task1 = copy.deepcopy(task1)
    new_task2 = copy.deepcopy(task2)

    new_duty1.remove_task(new_task1)
    new_duty1.remove_task(new_task2)
    new_duty2.insert_task(new_task1)
    new_duty2.insert_task(new_task2)
    if new_duty1.check_feasibility() and new_duty2.check_feasibility():
        return [new_duty1, new_duty2]
    else:
        return False

def doubleSplitRemoveInsertNeighborhoodOperator(duty1, task1, task2, duty2, duty3):
    new_duty1 = copy.deepcopy(duty1)
    new_duty2 = copy.deepcopy(duty2)
    new_duty3 = copy.deepcopy(duty3)
    new_task1 = copy.deepcopy(task1)
    new_task2 = copy.deepcopy(task2)

    new_duty1.remove_task(new_task1)
    new_duty1.remove_task(new_task2)
    new_duty2.insert_task(new_task1)
    new_duty3.insert_task(new_task2)
    if new_duty1.check_feasibility() and new_duty2.check_feasibility() and new_duty3.check_feasibility():
        return [new_duty1, new_duty2, new_duty3]
    else:
        return False


