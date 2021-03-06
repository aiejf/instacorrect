# InstaCorrect
End-to-end implementation of a **character-based self-attention sequence-to-sequence** (french) spell checker: www.instacorrect.com
* Data gathering and pre-processing
* Model definition
* Training and inference
* Model serving
* Front-end interaction


## Introduction
The ultimate goal of the project is to have a model that can effectively correct any french sentence for spell and grammatical errors. To this end, this project combines the architecture from [*Sentence-Level Grammatical Error Identification as Sequence-to-Sequence Correction*](https://arxiv.org/abs/1604.04677) and [*Attention Is All You Need*](https://arxiv.org/abs/1706.03762) to create a **character-based self-attention sequence-to-sequence model**.

## Background
Error correction can be seen as translation task, where to goal is to translate a sentence with grammatical and orthographic errors into correct sentence (Schmaltz et al., 2016).

Recent work in statistical machine translation (SMT) that achieved state of the art results made use of sequence-to-sequence models.  Most architectures use a recurrent neural network (RNN) for the encoder, and a second RNN, coupled with an attention mechanism for the decoder (Luong et al., 2015). While powerful, this architecture suffers from two drawbacks: first it is hard to train, as each timestep depends on the completion of the previous step in the RNN. Second it is hard for an LSTM network cell to carry information from the beginning of a sentence until the end of sentence (Vaswani et al., 2017).

Recently, the Google Brain team released a new sequence-to-sequence model that did not use an RNN but instead used a self-attention mechanism. Instead of being analyzed sequentially, each input is compared against its peers to produce a deep representation of the inputs. As there is no sequentiality, the training can be easily parallelized (Vaswani et al., 2017).

Traditional translation SMT models use a fixed word embeddings matrix to represent each words. This is not acceptable for a spell checker as it needs to adapt to an infinite vocabulary size (new words + mispellings). We can overcome this limitation by using a convolutational neural network in the encoder (Kim et al., 2015) and byte pair encoding in the decoder.


## Data Gathering and Pre-Processing
In *Sentence-Level Grammatical Error Identification as Sequence-to-Sequence Correction*, the authors use the Automated Evaluation of Scientific Writing (AESW) 2016 dataset. It is a collection of nearly 10,000 scientific journal articles with corrections annotated with professional editors (Schmatlz et al., 2015).

Unfortunately, there exist no such dataset for French. The workaround is to generate artificial errors in a correct corpus, namely the french translations from the [*European Parliament Proceedings Parallel Corpus 1996-2011*](http://www.statmt.org/europarl/), and news articles from the [*News Crawl: articles from 2014*](http://www.statmt.org/wmt15/translation-task.html). The resulting dataset contains around 13,000,000 sentences. We can now generate artificial grammatical mistakes in this dataset.

The generation of grammatical mistakes is performed using regular expressions. For example, one regular expression could look for words ending with *er* and replace them with *é*. Another could look for *laquelle* and replace it with *lequel*. For more information, refere to [this repository](https://github.com/maximedb/artificial_errors_generation).

Now that we have a set of erroneous sentences along with their correction, we can generate the vocabularies and the input file. As the input to the model is character based, we will go through the entire corpus and make a character vocabularry (of around 300 characters). For the output of the model, we will use byte-pair-encoding (Senrich et al., 2015) as in *Attention Is All You Need*. This method will create a fixed vocabulary (15,000 entries in our case) of the most frequent character pairs in the corpus. This allows the model to break previously unseen words in multiple tokens, eliminating the problem of out-of-vocabulary errors.


## Model
The model is a combination of the work of Schmatlz et al., 2014  and and Vaswani et al., 2017. It implements a **character-based self-attention sequence-to-sequence model**.

#### Character based convolution
The input to the model is a matrix of `[batch_size, sentence_length, word_length]`. The first step is to use an embedding matrix to replace each character integer with a fixed size vector (the embedding) that is learned during the traning process. Our inputs now have the following shape: `[batch_size, sentence_length, word_length, char_embedding_size]`. 

The next step is to apply a convolution on each word in the inputs. Each word can be represented as a matrix of size: `[word_length, char_embedding_size]`, more or less like black and white picture. Next, we apply a 1D convolution with several filters sizes (2, 3, 4 and 5) with 200 kernels. After each convolution, a non-linearity is applied along with a max-over-time pooling.
At the end of the process, each word is represented by a fixed size vector. The model is now able to process previously unseen words.
<p align="center"> 
  <img src="https://raw.githubusercontent.com/maximedb/instacorrect/master/Misc/kim.PNG" width="350" align="center">
</p>

#### Self-Attention
Instead of relying on RNN cells, self-attention models rely entirely on an attention mechanism to draw global dependencies between input and output (Vaswani et al., 2017). The following illustration from the Google Research Blog illustrates well the general intuition behind the model.

<p align="center"> 
  <img src="https://raw.githubusercontent.com/maximedb/instacorrect/master/Misc/transformer.gif" width="350" align="center">
</p>

A self-attention model is divided into two parts: the encoder and the decoder.

The encoder performs several steps of self-attention with its inputs as key, values and queries. Each word will be more or less represented as the weighted average of its projection against all of the other inputs in the sentence. At every step, each word is augmented with the information surrounding it. 

The decoding is performed in two steps. The first attention step is to compared the decoder's inputs against the ***encoder***'s outputs. The second attention step is to compare the result of the first step against the previously computed decoder's output.  

The final step is to perform a softmax on the logits of the final layer to draw of probability distribution over each possible token.

<p align="center"> 
  <img src="https://raw.githubusercontent.com/maximedb/instacorrect/master/Misc/attention.PNG" width="332" align="center">
</p>

Besides self-attention, the architecture implements many other elements:
- __Positional encoding__: each input and output is added (yes addition) to a positional vector that is dependent on its position on the sequence, to give a sense of position to the model.
- __Multi-head attention__: each input is projected h times with different learned projections. According ot Vaswani et al. it allows the model to jointly attend to information from different representations subspaces at different positions.
- __Residual connection__: at each node in the self-attention model, the input of this node is added to the output of the model.
- __Layer Normalization__: at each node the output of the model is normalized.
- __Label Smoothing__: at each node the output of the model is normalized.
- __Attention Dropout__: at each node the output of the model is normalized.

At training time, the model must predict the right output given the encoder's output and the decoder input.
This means that we can train the entire model at once, without waiting for the previous output to finish, speeding up the training time. To prevent the model from looking "into the future", the future's decoder inputs are masked et training time.

During inference, the logic is a bit different since we do not have the decoder's input. We must then implement a while loop that will compute each timestep. The inputs for each timestep is the encoder's output and all the previously generated output (the first one being the "GO" id, as during training).

## Results
The training and inference is done using a Tensorflow estimator. It is really useful and lets you focus on the essential part of the model and not the usual plumbing associated with running a tensorflow model. Furthermore, it is really easy to export a trained model using an estimator. The model reads examples using a tf.dataset. This functionality is great to read large files that would not fit into memory. Furthermore, there is a **dyanmic padding and bucketing** of the examples as to optimize the training time.

## Discussion

## Conclusion
Once a model is trained, it can be exported. It can be served to the "real world" with tensorflow serving. Tensorflow serving is not the easiest thing to grasp. It is not well documented, uses C++ code, the installation process is not clear, etc. Tensorflow serving is a program that lets you put your model on a server. This server accepts gRPC requests and returns the output of the model. In theory it sounds easy, in practice it not that easy.

Google released a binary that you can download using apt-get. This makes it much more easier. You just download this binary and execute it. It will launch your server. This server expects to find exported models in a directory you specified. In this directory you simply copy-paste your saved model from earlier. That's it. You can customize it more, but it does the job.

Now that's great. But it's not really user-friendly to ask your users to make gRPC request to your server. That's why you also need a simple application that can link the two together. Here I implemented a simple Flask application, that displays a simple website and exposes a single API function `is_correct`. When you make a POST request to this end-point with a text, it splits your text into sentences and calls the tensorflow-serving server with each sentences. It then multiplies the correct probabilities together to have a global correctnes probability and finally returns it to the front-end application.

All these applications are bundled together using Docker Compose and live on a DigitalOcean (mini) droplet.

## Front-end Application
A basic front-end application that runs angularjs to take the text written and send an AJAX request to the Flask app.

## Results and conclusion
The model achieves an accuracy of 95% on the validation set. This is already great! But in practice the model fails to detect basic errors. This is probably due to two things:
* The mistake generator is not really good. It generates unlikely mistakes more than likely mistakes. Your model is only as good as the quality of your data.
* The decoder vocabulary is limited to 50,000 words.

## Next Steps
The next model will need to have a larger decoder vocabulary as this is really limiting the current model. One way to do this would be to use convolutional embedding in the decoder as well. To improve the traning time, I will implement the transformer model from [Attention is all you need](https://arxiv.org/abs/1706.03762).

## Contributions
Feel free to contribute/comment/share this repo :-)
