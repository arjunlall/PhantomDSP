# Phantom DSP
Get 3D virtualized studio monitor sound from your headphones.

What is it?
HeadphoneEQ is a set of digital signal processing (DSP) filters that allow headphones to emulate listening to well tuned near field studio monitor speakers. Put simply, music sounds like it is coming from professional grade speakers in front of you instead of your headphones. The virtual speakers are modeled after measurements of the JBL M2 Reference Monitors and provide authoritative clean bass, well balanced midrange and a revealing high end. The EQ curve has two parts, first to equalize the differences between different headphones and second to adjust the response to match both measurements of the JBL M2 Reference Monitors and the Harman Target Response curve.

HeadphoneEQ works on top of EqualizerAPO, a piece of windows software that allows low level access to system audio. (https://sourceforge.net/projects/equalizerapo/)

Features
* Very low audio delay (~5ms)
* Coherent time domain in bass

Supported Headphones
* Sennheiser HD650/HD6XX
* Sennheiser HD800s
* Sennheiser IE800
* Audeze LCD-2 (Both pre and post fazor)
* Focal Elear

Things to be aware of
* Measurements for the HRTF (Head Related Transfer Function) were made based on my own head and ears. Since everyone has different features the imaging of the virtualized speakers may not be as precise person to person.

Installation Instructions
* Download and install EqualizerAPO if you don't already have it https://sourceforge.net/projects/equalizerapo/
* Restart your computer if you just installed EqualizerAPO
* Extract the contents of this git repo into the C:\Program Files\EqualizerAPO\config folder
* Open the config.txt file and uncomment the lines for your particular headphones. If you do not have any of the headphones I have buit a custom tuning for I suggest you use the HD800s filters, which are on by default, but feel free to try out others if you want to see what might sound best
* FYI - as soon as you make changes to the config.txt file your audio will change so be careful if you are listening to audio as you make the changes in case things get loud
* After the filters are on the sound level will probably be lower so you may need to turn your volume up to compensate

Credits / Thanks
* Warren Tenbrook
* Tyll Hertsens
* Harman International
* Paul Barton