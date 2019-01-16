from multiprocessing import Process, Value, Lock
from sysv_ipc import MessageQueue, IPC_CREAT
import random
from time import sleep
import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from sys import exit
from os import getpid, getppid, kill
from signal import signal, SIGUSR1, SIGUSR2

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


#Important: When the graphs appear close them and then press CTRL+Z on the terminal to safely close the program.



class Home(Process):

	numberOfHomes=0

	def __init__(self, consumptionRate, productionRate, isGenerous):
		super().__init__()
		Home.numberOfHomes+=1
		self.budget=10000000
		self.consumptionRate=consumptionRate
		self.productionRate=productionRate
		self.day=1
		self.energy=0
		self.homeNumber=Home.numberOfHomes
		self.messageQueue=MessageQueue(self.homeNumber,IPC_CREAT)
		self.isGenerous=isGenerous
		self.budgetSeries=pd.Series()
		

	def run(self):

		while 1:
			print("Home {}: It is day {}. My budget is {} dollars.".format(self.homeNumber, self.day, self.budget))
			self.budgetSeries=self.budgetSeries.append(pd.Series([self.budget], index=[self.day]))
			self.energy=self.productionRate-self.consumptionRate
			self.decideWhatToDo()
			if self.budget<0:
				print("Home {}: Shit I'm broke!".format(self.homeNumber))
				self.sendMessage('Broke')
				self.showBudgetGraph()
				break
			self.finishCurrentDay()
			self.waitForNextDay()
			self.day+=1
			# sleep(1)


	def showBudgetGraph(self):

		self.budgetSeries.plot()
		plt.xlabel('Day')
		plt.ylabel("Home{}'s Budget".format(self.homeNumber))
		plt.show()



	def finishCurrentDay(self):
		self.sendMessage('Done')

			
	def waitForNextDay(self):
		message=self.receiveMessage()


	def decideWhatToDo(self):
		
		if self.energy<0:
			self.getEnergy()
			if self.energy<0:
				self.buyEnergy()
		elif self.energy>0:
			if self.isGenerous:
				self.giveEnergy()
			else:
				self.sellEnergy()


	def sendMessage(self, message):

		amount=abs(self.energy)
		message= str(self.homeNumber) + " " + str(amount) + " " + message
		MessageQueue(100).send(str(message).encode())
		# print("Home{} sent: {}".format(self.homeNumber,message))
		

	def receiveMessage(self):

		x, t = self.messageQueue.receive()
		message = x.decode()
		# print("Home{} recieved: {}".format(self.homeNumber, message))
		return message


	def buyEnergy(self):

		print("Home {}: What's the price? I wanna buy some energy.".format(self.homeNumber))
		self.sendMessage('Buy')
		price=int(self.receiveMessage())
		print("Home {}: It seems the price is {} dollars.".format(self.homeNumber,price))
		self.budget+=self.energy*price


	def sellEnergy(self):

		print("Home {}: What's the price? I wanna sell some energy.".format(self.homeNumber))
		self.sendMessage('Sell')
		price=int(self.receiveMessage())
		print("Home {}: It seems the price is {} dollars.".format(self.homeNumber,price))
		self.budget+=self.energy*price

	def getEnergy(self):

		print("Home {}: I wanna get some free energy.".format(self.homeNumber))
		self.sendMessage('Get')
		amount=int(self.receiveMessage())
		if amount==0:
			print("Home {}: Dammit there's no free energy, I have to buy some.".format(self.homeNumber))
			return
		else:
			print("Home {}: Nice! I got {} free energy.".format(self.homeNumber, amount))
		self.energy+=amount
		if self.energy==0:
			print("Home {}: Perfect! I have all my energy needs covered.".format(self.homeNumber))
		else:
			print("Home {}: Oh, it's not enough. I still have to buy some energy.".format(self.homeNumber))

	def giveEnergy(self):

		print("Home {}: I'm giving away some free energy.".format(self.homeNumber))
		self.sendMessage('Give')
		amount=int(self.receiveMessage())

		if amount>0:
			print("Home {}: Cool! I gave away {} free energy.".format(self.homeNumber, amount))
		elif amount==0:
			print("Home {}: Oh, no one wants my free energy. I'll have to sell it.".format(self.homeNumber))
			self.sellEnergy()




class Market(Process):

	def __init__(self, numberOfHomes):

		super().__init__()
		self.numberOfHomes=numberOfHomes
		self.numberOfHomeThatAreDone=0
		self.numberOfHomeThatAreDoneLock=Lock()
		self.priceLock = Lock()
		self.fLock=Lock()
		self.aliveHomes=[True]*numberOfHomes
		self.price=20000
		self.gamma=.999999  # long-term attenuation coefficient for
		self.f=0		# internal factor (amount bought-amount sold)
		self.alpha=5	# modulating coefficient for factor for internal factors
		self.freeEnergy=0
		self.freeEnergyLimit=10
		self.day=1
		self.messageQueue=MessageQueue(100,IPC_CREAT)
		# print("Market: My messageQueue is {}",format(self.messageQueue))
		self.priceSeries=pd.Series()



	def run(self):

		

		# print('Market: My PID is {}.'.format(getpid()))

		signal(SIGUSR1, self.handleSignals)
		signal(SIGUSR2, self.handleSignals)

		external=External()
		external.start()

		

		Thread(target=self.handleMessages).start()

		sleep(3)
		self.showPriceGraph()


		# while True:
  # 			pass


	def updatePrice(self):
		with self.priceLock:
			self.price=int(self.gamma*self.price+self.alpha*self.f)
			self.priceSeries=self.priceSeries.append(pd.Series([self.price], index=[self.day]))
			with self.fLock:
				self.f=0
			if self.price<100:
				self.price=100
			print("Market: Updated the price. It is now {}.".format(self.price))



	def showPriceGraph(self):
		self.priceSeries.plot(colormap='autumn')
		plt.xlabel('Day')
		plt.ylabel('Price of Energy')
		plt.show()

		
	def handleSignals(self, sig, frame):
		if sig == SIGUSR1:
			with self.priceLock:
				self.price+=5000
				print("Market: Signal from External received. Macron has increased the tax on energy! The price is increased by 5000. The energy now costs {} euros per unit.".format(self.price))
		elif sig == SIGUSR2:
			with self.priceLock:
				self.price-=10000
				print("Market: Signal from External received. INSA students found a way to perform efficient nuclear fusion! The price is decreased by 10000. The energy now costs {} euros per unit.".format(self.price))



	def goToNextDay(self):

		# print("numberOfHomeThatAreDone:{}, numberOfHomes:{}".format(self.numberOfHomeThatAreDone,self.numberOfHomes))

		if self.numberOfHomeThatAreDone==self.numberOfHomes:
			self.numberOfHomeThatAreDone=0
			self.day+=1
			print("\n")
			print('Market: IT IS DAY {}!'.format(self.day))
			self.updatePrice()
			for i in range (1,len(self.aliveHomes)+1):						
				if self.aliveHomes[i-1]:
					self.sendMessage(i,'Go')




	def handleMessages(self):
		with ThreadPoolExecutor(max_workers=3) as executor:
			executor.submit(self.waitForMessage)


	def waitForMessage(self):

		while 1:
			message=self.receiveMessage()
			message=message.split()
			homeNumber=int(message[0])
			amount=int(message[1])
			message=message[2]

			if message=='Broke':
				print('Market: Oh no! Home{} went broke.'.format(homeNumber))
				self.aliveHomes[homeNumber-1]=False
				print(self.aliveHomes)
				self.numberOfHomes-=1 #lock
				print('Market: Henceforth there are {} homes.'.format(self.numberOfHomes))

				if self.numberOfHomes==0:
					self.numberOfHomes=100 #i would love to find out a way to make the program stop at this point
				self.goToNextDay()

			elif message=='Buy':
				with self.priceLock:
					print('Market: The price of energy is {} dollars.'.format(self.price))
					self.sendMessage(homeNumber, self.price)
				print('Market: Demand is up, increasing the price.')


				with self.fLock:
					self.f+=1


			elif message=='Sell':
				with self.priceLock:
					print('Market: The price of energy is {} dollars.'.format(self.price))
					self.sendMessage(homeNumber, self.price)
				print('Market: Supply is up, decreasing the price.')


				with self.fLock:
					self.f-=1
				
			elif message=='Give':
				print('Market: WOW! Home{} is giving away {} units of energy for free!'.format(homeNumber, amount))
				if self.freeEnergy>=self.freeEnergyLimit:
					print('Market: Woah slow down! I have way too much free energy.')
					self.sendMessage(homeNumber, 0)
				else:
					self.freeEnergy+=amount
					self.sendMessage(homeNumber, amount)
				print('Market: Currently {} units of free energy available'.format(self.freeEnergy))
				
			elif message=='Get':
				print('Market: LOL! Home{} wants {} units of energy for free!'.format(homeNumber, amount))
				if self.freeEnergy>=amount:
					self.sendMessage(homeNumber, amount)
					self.freeEnergy-=amount
					print('Market: Currently {} units of free energy available'.format(self.freeEnergy))
				else:
					self.sendMessage(homeNumber, self.freeEnergy)
					self.freeEnergy-=0
					print('Market: Currently no free energy is available'.format(self.freeEnergy))

			elif message=='Done':
				print('Market: Home{} is done.'.format(homeNumber))
				with self.numberOfHomeThatAreDoneLock:
					self.numberOfHomeThatAreDone+=1
				self.goToNextDay()

			


	def sendMessage(self, homeNumber, message):

		MessageQueue(homeNumber).send(str(message).encode())
		# print("Market sent: {}".format(message))


	def receiveMessage(self):

		x, t = self.messageQueue.receive()
		message = x.decode()
		# print("Market recieved: {}".format(message))
		return message



class External(Process):

	def __init__(self):
		super().__init__()


	def run(self):
		marketPID=getppid()
		# print("External: Market's PID is {}.".format(marketPID))

		sleep(.1)
		kill(marketPID,SIGUSR1)

		sleep(.2)
		kill(marketPID,SIGUSR2)

		sleep(.1)
		kill(marketPID,SIGUSR1)





class Weather(Process):
	def __init__(self):
		super().__init__()
		

	def run(self):
		while 1:
			current=datetime.datetime.now()			#We get the current date and time and use them to get the temperature.

			if current.month==1:
				temperature.value=3
			elif current.month==2:
				temperature.value=5
			elif current.month==3:
				temperature.value=8
			elif current.month==4:
				temperature.value=11
			elif current.month==5:
				temperature.value=16
			elif current.month==6:
				temperature.value=19
			elif current.month==7:
				temperature.value=22
			elif current.month==8:
				temperature.value=22
			elif current.month==9:
				temperature.value=18
			elif current.month==10:
				temperature.value=13
			elif current.month==11:
				temperature.value=8
			elif current.month==12:
				temperature.value=4


			
			#...
			#...
			#Do something similar with hour.






			print("Weather: The datetime is {}.".format(current))


			sunny.value=random.randint(0,2)					#50% sunny 50% cloudy
															#or we could do something similar to temperature where we use the months and hours to determine the probability
															#but for now it's ok



			if sunny.value:
				print("Weather: The temperature is {}°C and it is sunny.".format(temperature.value))
			else:
				print("Weather: The temperature is {}°C and it is cloudy.".format(temperature.value))

			sleep(1)





def clean():									#To clean the message queues.
	clear=MessageQueue(100,IPC_CREAT)
	clear.remove()

	clear=MessageQueue(1,IPC_CREAT)
	clear.remove()							

	clear=MessageQueue(2,IPC_CREAT)
	clear.remove()	

	clear=MessageQueue(3,IPC_CREAT)
	clear.remove()	

	clear=MessageQueue(4,IPC_CREAT)
	clear.remove()	

	clear=MessageQueue(5,IPC_CREAT)
	clear.remove()	


if __name__=="__main__":


	clean()



	temperature=Value('d', 12.5)
	sunny=Value('i', 1)  					# 1: sunny, 0: cloudy



	# weather=Weather()						#Weather is optional at the moment.
	# weather.start()




	market=Market(4)
	market.start()
	

	home1=Home(10, 0, True)
	home1.start()


	home2=Home(11, 10, True)
	home2.start()


	home3=Home(9, 9, False)
	home3.start()


	home4=Home(9, 2, True)
	home4.start()


	# home5=Home(5, 0, True)
	# home5.start()