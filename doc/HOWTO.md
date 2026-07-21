# Introduction

This section is to explain how I managed to find out how my device works. Hope this will be helpful for people who want
to do the same.

Once you have figured out how your device works (header, encoding, transport), there are two ways to add it to the
application:

- **Generic device (recommended)**: describe the device in the gui or in a small YAML file, no code needed. See
  [Adding a generic device](#adding-a-generic-device-no-code).
- **Native device**: write a Python device class, for protocols the generic driver cannot express. See
  [Adding a native device](#adding-a-native-device-python-code).

# Application description

The application is divided in two parts:

- The gui which is made to help configure and customize what is displayed on the screen.
- The device_controller which is the part that talks to the device. Since v2.0 it runs inside the gui process (no
  separate root service), device access is granted by udev rules.

Configuration files:

- gui_config.yaml: holds the configuration of the gui. The config file is under resources.
- device_{id}.yaml: one file per registered device, holding its description (VID/PID, resolution, transport, encoding,
  header...). Created by the gui or by hand, under the config directory.
- config_{id}.yaml: holds the configuration of what the device will display, keyed by device id. Such as background,
  foreground and the metrics to display.
- config_{width}{height}.yaml: resolution-keyed default themes, used to seed the per-device config the first time.
  Predefined config files are under resources/config.

The config directory is `resources/config` when running from the sources, and `~/.config/thermalright-lcd-control/config`
for an installed application.

Main class:

- main_app.py: the main class that starts the application (gui + device controller).

To run from the sources:

```bash
uv run thermalright-lcd-control-app --config resources/gui_config.yaml
```

# Tools

- Install a windows VM on virtualBox and install the official product software.
- Install wireshark.
- Install tshark command line tool.

# Configuring the official product software

On the windows VM, configure the display with simple color background with no foreground or text. Really just the
background.
I found out that the offcial product software adds many sequences of 0x00 in the paquet, for report id and as separator
for each raw of pixels.

I used to find it because I used the green background available in the official product software. It's hexadecimal does
not contain 0x00 at all.
Which means that all the 0x00 are part of the extra technical information added.
For each packet sent, there is a header that is added, and it's been challenging to fid its value until I used the green
background.

Save your configuration and make sure that if you restart the software, it will use the same configuration.

# Capturing packets

You need to run this command to make wirehsark reading usb packets.

```bash

  sudo modprobe usbmon

```

Use lsusb command to find out the usb Bus id and device id. Something like this:

![lsub](lsusb.png)

In my case, the Bus id is 3 and the device id is 4.

Run wireshark with sudo, when it opens, select usbmon{Bus id}. In my case, it is usbmon3.

To find the packets sent to the device, you need to use this filter to have the packets you want:

```
    usb.device_address == {device id} && usb.transfer_type == 0x01 && usb.endpoint_address == 0x02 && usb.src == "host" 
```

- usb.device_addressm: The device id, in my case 4.
- usb.transfer_type: 0x01 for data transfer.
- usb.endpoint_address: 0x02 for data transfer.
- usb.src: host for data transfer.

If the application is running and the filter does not show any packets, remove usb.transfer_type and
usb.endpoint_address one by one and see if it works.

And try to find the correct value for the one that does not work. To do this:

- Select a paquet with the biggest length.
- Unfold the USB URB section.
- For usb.transfer_type, you can add the correct value by doing a right-click on "URB transfert type" and selecting "
  Apply as Filter" -> "...and Selected".
- For usb.endpoint_address, you can add the correct value by doing a right-click on "Endpoint" and selecting "Apply as
  Filter" -> "...and Selected".

In windows VM, keep the software running and disable the display usb from USB settings of virtualBox here:

![disable_usb.png](disable_usb.png)

Then go back to wireshark and restart the capture. If you are asked to save just select "Continue without saving".

Since wireshark filter is applied and USB on VM is disabled, you should not see any packets in Wireshark.

After that, enable the display usb from USB settings of virtualBox and wait to see packets in wireshark.

Click on stop after about a second from the time you see packets.

Then go to File -> Export Specified Packets, choose folder and name of the file then click save.

# Extract the data from the wireshark file

The wireshark can oonly be read by wireshark. This section is to explain how I managed to extract the data from the
wireshark file into simple text file in hexadeciamal format.

On terminal run this command:

```bash

  tshark -r /path-to-capture/yourcapturefile.pcapng -T fields -e usb.capdata > output.txt
  
```

In fields section, there is two possible values (or at least the ones that I've dealing with):

- usb.capdata : If in wireshark the section where the data is displayed is called "Leftover capture data"
- usbhid.data : If in wireshark the section where the data is displayed is called "HID Data"

Check output.txt if it contains the data you want.

# Clean output.txt

Even if you hit the "Stop" button in wireshark quickly, you will end up with multiple occurrences of the packets that
represent the image sent to the device.
The output.txt under doc section in this repository is an example of what you should get.
To clean the output.txt:

- I never understood what the first line of the file is for. It works even without duplicating it in my implementation.
  If you have one similar I think you can go and remove it.
- The second line is the beginning of the group of packets that represent the image sent to the device.
- To find the next occurrence and then remove all lines starting from there to the end.
- After cleaning the file, you end up with one like output_clean.txt.
- The hexadecimal representation of the image is a sequence of f597.
- And the header value is all hexadecimal characters that are before the first f597. And it is '
  dadbdcdd02000100f000400102000000005802000000'
- In the last line there is a sequence of 00 after the last f597. This is because the last part of the image is less
  than 512 bytes so it is padded with 00.
- Between every sequence of f597 there is a sequence of 0000, this sequence is added every 956 characters.
  This sequence is used as a separator for every row, In my case, the image is scanned from bottom to top and from left
  to right.
  So every time it hits the top, the sequence of 0000 is added.

# Adding a generic device (no code)

At this stage you know the header value, the image encoding and the transport your device uses. In most cases that is
all the generic, data-driven driver needs: you just have to describe the device, either from the gui or in a YAML
file.

## From the gui

The easiest way to add a device is the "add device" form. No file editing and no restart are required: once you save,
the device is registered and starts displaying immediately.

Steps:

1. Click the **"+" button** in the application header to open the add-device dialog.
2. Pick your device from the **connected devices list**. The dialog enumerates the USB devices currently plugged in
   (via `lsusb`), so you can select yours by name/VID:PID instead of typing the ids by hand.
    - If the selected VID:PID matches one of the bundled profiles (see [Bundled profiles](#bundled-profiles-known-devices)),
      the **whole form is pre-filled** for you — you can just save.
    - Otherwise, fill in the fields yourself (see [The device file](#the-device-file) for the meaning of each field:
      resolution, transport, encoding, header, and the transport-specific optional fields).
3. Leave the **"Generic" toggle on** to use the data-driven driver (recommended). Turn it off only if your device needs
   one of the native, hard-coded device classes.
4. Check the suggested **device id** — the dialog proposes `<pid>_<vid>_<bus>_<device>` so two identical displays stay
   distinct. You can keep it as is in most cases.
5. Click **Save**. The dialog writes the `device_<id>.yaml` file for you, the device appears as a new tab in the device
   bar, and it starts rendering right away with a default theme for its resolution.

If the device shows nothing or a blurry/scrambled image after saving, the header or encoding is not right yet: reopen
the form and adjust the `header` / `encoding` fields (see [The device file](#the-device-file) and
[The screen displays a blurry image](#the-screen-displays-a-blurry-image)).

## The device file

Each registered device is one `device_<id>.yaml` file in the config directory. Example for the 0416:5302 device:

```yaml
id: 5302_0416_3_4
vid: 0x0416
pid: 0x5302
width: 320
height: 240
generic: true
transport: hid
chunk_size: 4096
encoding: rgb565_le_columns
report_id: "00"
header:
  prefix: "DADBDCDD"
  format: "<6HIH"
  values: [2, 1, width, height, 2, 0, payload_size, 0]
```

Fields:

- `id`: unique device id, also used to name the active theme file (`config_<id>.yaml`). The gui suggests
  `<pid>_<vid>_<bus>_<device>` so two identical devices stay distinct.
- `vid` / `pid`: USB ids, as shown by `lsusb`.
- `width` / `height`: screen resolution in pixels.
- `generic`: `true` for the data-driven driver, `false` to use a native device class instead.
- `transport`: how frames are sent to the device. One of:
    - `hid`: HID interface (hidapi).
    - `usb_bulk`: plain USB bulk endpoint.
    - `usb_bulk_ly`: USB bulk with the "LY" handshake + chunked JPEG protocol.
    - `scsi`: USB Mass Storage / SCSI commands.
- `chunk_size`: size in bytes of each write. In wireshark it corresponds to `usb.data_len`.
- `encoding`: how the image is encoded. One of:
    - `rgb565_le_columns`: RGB565 little-endian, column-major with vertical flip.
    - `rgb565_be`: RGB565 big-endian, row-major.
    - `jpeg`: JPEG-compressed frame (see `jpeg_quality`).
- `header`: the frame header, either static or computed per frame:
    - Static: `header: {static: "dadbdcdd0200..."}` with the full hex string you extracted from the capture.
    - Computed: `prefix` (fixed hex bytes) + `format` (a Python
      [struct](https://docs.python.org/3/library/struct.html) format) + `values`. Each value is a literal int, a hex
      string, or one of the placeholders `width`, `height`, `payload_size`, `cmd`, resolved for every frame.
    - Omit `header` entirely if your device takes the raw payload with no header.

Optional fields, depending on the transport:

- `report_id`: hex byte(s) prepended to every HID packet (default `"00"`).
- `cmd`: value substituted for the `cmd` header placeholder.
- `command`: SCSI opcode for the `scsi` transport (default `0xF5`).
- `jpeg_quality`: JPEG quality for the `jpeg` encoding (default 85).
- `ep_in`: IN endpoint address used to read handshake replies (default `0x81`).
- `start_wait`: seconds to wait before sending the first frame.

## Bundled profiles (known devices)

The profiles of already-reverse-engineered devices are bundled under
`src/thermalright_lcd_control/device_controller/display/known_devices/`, one YAML file per device+resolution (named
`<VID>x<PID>_<width>x<height>.yaml`). The gui uses them to pre-fill the add-device form when a matching VID:PID is
connected.

If you got a new device working with the generic driver, please contribute your profile there so the next user gets it
pre-filled.

# Adding a native device (Python code)

If your device protocol cannot be expressed with the generic driver (special handshake, exotic encoding...), you can
implement a device class. An example with commentary is available in
`new_device_example.py`.

For naming class please use the convention in the `new_device_example.py`, please don't name the class using your
product name because the same VID/PID can be used in multiple products.

You're free to add new python file for the device or :

- Add it in `hid_devices.py` file, if the device uses hid interface.
- Add it in `usb_devices.py` file, if the device uses usb interface.

If you choose to add a new file, make sure you put vid/pid in file name for example `device_0418_5304.py`.

And then add your device in `SUPPORTED_DEVICES` variable in `supported_devices.py` file.

In `resources/config`, there is pre-configured themes for different screen resolutions. Files are named as config_
{width}{height}.yaml.

If there is no theme for your screen resolution, you can create one by duplicating any of the available files

Update the config file, replace `/usr/share/thermalright-lcd-control` with  `./resources`.

If you added a new file, disable foreground by updating property `foreground.enabled` to `false` in the config file.

Later you can create a folder under `resources/themes/forgrounds/{width}{height}` and add foregrounds suited for your
screen resolution.

Finally, register the device with `generic: false` in its `device_<id>.yaml` file (see the generic section above): the
native class is resolved from the VID/PID and resolution.

Make sure you stopped the windows VM and then start the application:

```bash
uv run thermalright-lcd-control-app --config resources/gui_config.yaml
```

If you're done well all the steps, you should see your device working.

# The screen displays a blurry image

I think that ThermalRight used the same logic to encode the image in the official product software. Finally, I hope so.

If the screen displays a blurry image, it means that the image is not encoded correctly.

For a generic device, first try the other `encoding` values in the device file — that is often enough. If none of them
works, you need to find out how the image is encoded for your device and implement it in a native device class.

There is many ways to scan image, horizontal scan, vertical scan and from rigtht to left or left to right.

To figure out how the image is encoded, you need two simple color bars images, one horizontal and one vertical.
Use images with the same resolution as the screen.

Redo all steps to capture packets for these images until ending with a clean output file.

Using the green image result you can find out the value of the row separator, it could be something like the '0000'
sequence, and count the number of hexa character between two separators.

From the three files remove header and the tailing zeros from last line. Maybe it is not zero but other value but
you can find it thanks to the green image, everything after the last f597 should be removed.

Also, remove the '\n' or '\r' at the end of each line.

I used AI to figure out how image is encoded, I gave it the three images, their output explained to it the separator
logic.

Then asked it to figure out the encoding algorithm. To make sure that he give me the good one,
I tell it to generate an output file with the code and compare it to the ones that I gave it.
If it is not exactly the same then it must try another algorithm and so on until it finds the good one.

It took me a lot of time and effort to figure out how to prepare something clean for that AI can figure out how to
encode the image.

# Making the device visible in the gui

There is nothing more to do: the gui reads the same `device_<id>.yaml` files. Once the device is registered (via the
"+" dialog or by dropping the file in the config directory), it appears in the device list and gets its own active
theme file `config_<id>.yaml`.

I deliberately avoided putting a product name like `Frozen Wareframe` because the same device can be used in multiple
products, and therefore the concept of a product name loses all meaning.

# Add foreground images for the new device

If your device resolution does not match any of the pre-configured foregrounds, you can create a new folder under
`resources/themes/forgrounds/{width}{height}` and add foregrounds suited for your screen resolution.

You can get the ones under the official product software. For those already copied here, I used the ones under
`TRCCAPEN\Data\USBLCD\Web`.

Foregrounds are files under folders `zt*`, pick the one that matches your screen resolution. The folders contain
subfolders with the foreground image a config file and a preview of the theme. Just pick the png files and copy them
under `resources/themes/forgrounds/{width}{height}`.

# Add a new theme

Last step is to run the application (`uv run thermalright-lcd-control-app --config resources/gui_config.yaml`),
configure a theme and save it.

The config file will be saved in `resources/themes/presets/{width}{height}/`.

Copy that file to `resources/config/` and rename it to `config_{width}{height}.yaml`. 
Open the file and change the`resource/` to `/usr/share/thermalright-lcd-control/`.

This theme will be used as default theme for new installations.

# Conclusion

That's it, now application is ready to be packaged and installed.
