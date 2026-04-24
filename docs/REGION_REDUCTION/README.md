# REGION REDUCTION

I need to try adding some downscaling support to this app. I think we should start with simple resizing, implementing the standard Photoshop-style suite of downsampling algorithms (nearest neighbor, bicubic sharper, bicubic, bilinear, etc). We can support whatever you think as far as ways to define the downscaling - mulitiplier (e.g. 2x - or 0.5x depending on what is eaiser for the user to understand) as well as target size (e.g. 100px). So I think the first step would be to add these, along with an argument that lets me tell the app to 'resize and stop', which would output the resized image and exit, so that I could look at them and compare.

Then I'll be looking for a way to downscale these pixel art images and make them still look nice (not blurry like most of the filters do because they antialias). I would say that generally nearest neighbor would be the right approach, but the purpose of downsamping is to reduce the number of discrete segments in the final 3MF file. Let me explain with an example:

samples\input\large\sf2_ryu_level.png gets converted to a 3MF file with over 10k segments (objects in the mesh), even with region merging. This has a very detrimental effect on multiple things - such as a long print time, inability to manipulate the object in the slicer due to its complexity, difficulty in coloring regions due to sheer number of regions, etc.

So the ultimate goal with downscaling is to get less regions in the final output.

I was looking at Makerworld's Image to Keychain processor on Makerlab, which processes an image to downscale it for creating a keychain. It doesnt seem to use any of these kinds of resizing algorithms - the resulting image comes out looking very smooth but not filtered, looking more like 'designed' vector curves.

To see an example, look at the two images in the folder along with this file:

- original.png - the original input pixel art
- keychain.png - the processed 'vector-style' pixel art

I believe an important distinction that I'm realizing is that they aren't *necessarily* just resizing the image down; their algorithm is focused on reducing regions, not necessarily on resizing. By converting it into vector-ish geometry, I supposed you could resize it as well, but I dont have a hard requirement to *actually* resize the image down either; the ultimate goal here is to reduce the final region count.

In the case of the image that I need to reduce the region count in (samples\input\large\sf2_ryu_level.webp), I've also noticed something else worth mentioning; the image has a lot of, I'll call it, "pixel noise" (small 1+ pixel areas of color). Processing the file through the Makerlab Image to Keychain process removes all of that tiny 1+ pixel noise, which is one of the things driving the region count up so dramatically. I believe this is another valuable observation, because maybe we can try denoising the source pixel art first also, to see how much of a benefit that will have for region reduction; I suspect this alone would provide a pretty major improvement for very little work.

I think it might be a good idea to make a separate Python script to test these various ideas first, rather than implementing it right into the main code to start with. The new script could open the source file, try different things, output the preview images for each, along with metadata like the number of regions, number of regions reduced, percent reduced, and so on. We could iterate there and test before settling on something to promote to the main code. You can import whatever you need to use from the main code base where necessary.

I also have a document that I put together called /docs/SMOOTH_DOWNSCALING.md - this details a possible implementation of a Makerlab-like 'vectorization' approach to this problem. It might be something to look at, but it's not a trivial process.

And finally, if you have any ideas on how to make progress on this issue, I am completely open to suggestions. Do not treat this document or the other document I mentioned as prescriptive or mandatory. As I've said, the goal here is to reduce the number of regions as much as possible in the file I'm currently working with (samples\input\large\sf2_ryu_level.png).
